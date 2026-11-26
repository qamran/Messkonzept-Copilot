"""MKC-11.3: GET /api/admin/backup-status (admin only), with a `stale` flag.

The rows come from a dependency that the tests replace; tests/db checks the real query.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from mkc.api.app import create_app
from mkc.api.backup_status import BackupRunOut, latest_backup_runs
from mkc.config import Settings

ISSUER = "https://example-instance.clerk.accounts.dev"
ORIGIN = "http://localhost:5173"
NOW = datetime.now(UTC)


@pytest.fixture(scope="module")
def key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(key: rsa.RSAPrivateKey, role: str) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user_1",
        "iss": ISSUER,
        "azp": ORIGIN,
        "iat": now,
        "nbf": now - 5,
        "exp": now + 60,
        "role": role,
    }
    return jwt.encode(claims, key, algorithm="RS256")


def _run(state: str, hours_ago: float, **fields: Any) -> BackupRunOut:
    started = NOW - timedelta(hours=hours_ago)
    finished = None if state == "running" else started + timedelta(minutes=1)
    return BackupRunOut(started_at=started, finished_at=finished, state=state, **fields)


def _client(
    key: rsa.RSAPrivateKey, rows: tuple[BackupRunOut | None, BackupRunOut | None] | Exception
) -> TestClient:
    settings = Settings(clerk_issuer=ISSUER, clerk_authorized_parties=[ORIGIN])
    app = create_app(settings, key_resolver=lambda _t: key.public_key())

    def fake() -> tuple[BackupRunOut | None, BackupRunOut | None]:
        if isinstance(rows, Exception):
            raise rows
        return rows

    app.dependency_overrides[latest_backup_runs] = lambda: fake
    return TestClient(app)


def _get(client: TestClient, token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/api/admin/backup-status", headers=headers)


def test_needs_a_token_and_the_admin_role(key: rsa.RSAPrivateKey) -> None:
    client = _client(key, (None, None))
    assert _get(client, None).status_code == 401
    assert _get(client, _token(key, "")).status_code == 403


def test_never_ran_is_stale(key: rsa.RSAPrivateKey) -> None:
    body = _get(_client(key, (None, None)), _token(key, "admin")).json()
    assert body == {"state": "never", "last_run": None, "last_success": None, "stale": True}


def test_fresh_success(key: rsa.RSAPrivateKey) -> None:
    ok = _run("ok", 1, object_name="nightly/mkc-a.sql.gz", size_bytes=1146)
    body = _get(_client(key, (ok, ok)), _token(key, "admin")).json()
    assert body["state"] == "ok"
    assert body["stale"] is False
    assert body["last_success"]["object_name"] == "nightly/mkc-a.sql.gz"
    assert body["last_success"]["size_bytes"] == 1146


def test_success_older_than_26_hours_is_stale(key: rsa.RSAPrivateKey) -> None:
    ok = _run("ok", 27, object_name="nightly/mkc-old.sql.gz", size_bytes=1)
    body = _get(_client(key, (ok, ok)), _token(key, "admin")).json()
    assert body["state"] == "ok"
    assert body["stale"] is True


def test_failed_run_keeps_the_last_success(key: rsa.RSAPrivateKey) -> None:
    failed = _run("failed", 1, error="upload refused: HTTP 403")
    ok = _run("ok", 25, object_name="nightly/mkc-b.sql.gz", size_bytes=2)
    body = _get(_client(key, (failed, ok)), _token(key, "admin")).json()
    assert body["state"] == "failed"
    assert body["last_run"]["error"] == "upload refused: HTTP 403"
    assert body["last_success"]["object_name"] == "nightly/mkc-b.sql.gz"
    assert body["stale"] is False


def test_running(key: rsa.RSAPrivateKey) -> None:
    running = _run("running", 0.1)
    body = _get(_client(key, (running, None)), _token(key, "admin")).json()
    assert body["state"] == "running"
    assert body["stale"] is True


def test_database_error_gives_503_without_details(key: rsa.RSAPrivateKey) -> None:
    client = _client(key, RuntimeError("connection to postgresql://u:pw@host failed"))
    response = _get(client, _token(key, "admin"))
    assert response.status_code == 503
    assert "pw" not in response.text
