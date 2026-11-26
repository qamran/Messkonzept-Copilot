"""MKC-11.2: `mkc-backup`: pg_dump → gzip → upload, recorded in backup_runs.

No database and no network: pg_dump is a stub script, the upload goes to a local HTTP
server, and the recorder is in memory. The DB recorder has its own test in tests/db.
"""

import gzip
import http.server
import logging
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pytest

from mkc import backup
from mkc.config import Settings

PASSWORD = "s3cr3t-pw-123"
TOKEN = "par-token-abc987"
DB_URL = f"postgresql://mkc:{PASSWORD}@db.example:6543/mkc?sslmode=require"
NOW = datetime(2026, 11, 26, 2, 30, 0, tzinfo=UTC)
OBJECT = "nightly/mkc-20261126T023000Z.sql.gz"

STUB = """
import os, sys
assert "{pw}" not in " ".join(sys.argv), "password in argv"
assert os.environ.get("PGPASSWORD") == "{pw}", "PGPASSWORD missing"
assert os.environ.get("PGHOST") == "db.example" and os.environ.get("PGPORT") == "6543"
assert os.environ.get("PGSSLMODE") == "require"
for flag in ("--schema=public", "--no-owner", "--no-privileges"):
    assert flag in sys.argv, flag
if os.environ.get("STUB_FAIL"):
    sys.stderr.write("pg_dump: error: connection to server failed (password {pw})\\n")
    sys.exit(1)
sys.stdout.write("CREATE TABLE t (id int);\\n" * 1000)
""".replace("{pw}", PASSWORD)


@dataclass
class MemoryRecorder:
    rows: dict[int, dict[str, object]] = field(default_factory=dict)
    fail_start: bool = False

    def start(self, started_at: datetime) -> int:
        if self.fail_start:
            raise RuntimeError(f"database down ({PASSWORD})")
        run_id = len(self.rows) + 1
        self.rows[run_id] = {"state": "running", "started_at": started_at}
        return run_id

    def finish(self, run_id: int, **fields: object) -> None:
        self.rows[run_id].update(fields)


class _Receiver(http.server.BaseHTTPRequestHandler):
    received: ClassVar[dict[str, object]] = {}
    status: ClassVar[int] = 200

    def do_PUT(self) -> None:
        length = int(self.headers["Content-Length"])
        type(self).received = {"path": self.path, "body": self.rfile.read(length)}
        self.send_response(self.status)
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture
def receiver() -> Iterator[tuple[str, type[_Receiver]]]:
    handler = type("Receiver", (_Receiver,), {"received": {}, "status": 200})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/p/{TOKEN}/n/ns/b/mkc-backups/o/"
        yield url, handler
    finally:
        server.shutdown()


@pytest.fixture
def pg_dump_stub(tmp_path: Path) -> list[str]:
    script = tmp_path / "pg_dump_stub.py"
    script.write_text(STUB, encoding="utf-8")
    return [sys.executable, str(script)]


def _settings(upload_url: str, tmp_path: Path, *, allow_http: bool = True) -> Settings:
    # The local receiver speaks plain http; production links must be https.
    return Settings(
        database_url=DB_URL,
        backup_upload_url=upload_url,
        backup_dir=str(tmp_path / "work"),
        backup_allow_http=allow_http,
    )


def _run(settings: Settings, recorder: MemoryRecorder, pg_dump: list[str]) -> bool:
    return backup.run_backup(settings, recorder=recorder, pg_dump=pg_dump, now=lambda: NOW)


def test_success_uploads_the_gzipped_dump_and_records_ok(
    receiver: tuple[str, type[_Receiver]], pg_dump_stub: list[str], tmp_path: Path
) -> None:
    url, handler = receiver
    recorder = MemoryRecorder()

    assert _run(_settings(url, tmp_path), recorder, pg_dump_stub) is True

    assert handler.received["path"] == f"/p/{TOKEN}/n/ns/b/mkc-backups/o/{OBJECT}"
    body = handler.received["body"]
    assert isinstance(body, bytes)
    assert gzip.decompress(body).decode() == "CREATE TABLE t (id int);\n" * 1000
    row = recorder.rows[1]
    assert row["state"] == "ok"
    assert row["object_name"] == OBJECT
    assert row["size_bytes"] == len(body)
    assert row["finished_at"] == NOW
    # The local dump file is removed after the upload.
    assert list((tmp_path / "work").glob("*")) == []


def test_failed_dump_never_uploads_and_records_failed(
    receiver: tuple[str, type[_Receiver]],
    pg_dump_stub: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    url, handler = receiver
    monkeypatch.setenv("STUB_FAIL", "1")
    recorder = MemoryRecorder()

    with caplog.at_level(logging.INFO):
        assert _run(_settings(url, tmp_path), recorder, pg_dump_stub) is False

    assert handler.received == {}
    row = recorder.rows[1]
    assert row["state"] == "failed"
    assert "pg_dump" in str(row["error"])
    assert "backup failed" in caplog.text
    _assert_no_secrets(caplog.text, str(row))


def test_upload_error_records_failed_without_the_link(
    receiver: tuple[str, type[_Receiver]],
    pg_dump_stub: list[str],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    url, handler = receiver
    handler.status = 403
    recorder = MemoryRecorder()

    with caplog.at_level(logging.INFO):
        assert _run(_settings(url, tmp_path), recorder, pg_dump_stub) is False

    row = recorder.rows[1]
    assert row["state"] == "failed"
    assert "403" in str(row["error"])
    _assert_no_secrets(caplog.text, str(row))


def test_status_write_failure_does_not_stop_the_backup(
    receiver: tuple[str, type[_Receiver]],
    pg_dump_stub: list[str],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    url, handler = receiver
    recorder = MemoryRecorder(fail_start=True)

    with caplog.at_level(logging.INFO):
        assert _run(_settings(url, tmp_path), recorder, pg_dump_stub) is True

    assert handler.received["path"] == f"/p/{TOKEN}/n/ns/b/mkc-backups/o/{OBJECT}"
    assert "status not recorded" in caplog.text
    _assert_no_secrets(caplog.text)


def test_missing_upload_link_fails_before_dumping(
    pg_dump_stub: list[str], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    recorder = MemoryRecorder()
    with caplog.at_level(logging.INFO):
        assert _run(_settings("", tmp_path), recorder, pg_dump_stub) is False
    assert recorder.rows[1]["state"] == "failed"
    assert "MKC_BACKUP_UPLOAD_URL" in str(recorder.rows[1]["error"])


def test_upload_link_must_be_https(pg_dump_stub: list[str], tmp_path: Path) -> None:
    recorder = MemoryRecorder()
    plain = f"http://objectstorage.example/p/{TOKEN}/o/"
    settings = _settings(plain, tmp_path, allow_http=False)
    assert _run(settings, recorder, pg_dump_stub) is False
    assert "https" in str(recorder.rows[1]["error"])
    _assert_no_secrets(str(recorder.rows[1]))


def test_main_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backup, "run_backup", lambda *_a, **_k: True)
    assert backup.main() == 0
    monkeypatch.setattr(backup, "run_backup", lambda *_a, **_k: False)
    assert backup.main() == 1


def _assert_no_secrets(*texts: str) -> None:
    for text in texts:
        assert PASSWORD not in text
        assert TOKEN not in text
