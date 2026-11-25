"""MKC-10.1: the production origin and Vercel previews pass CORS and the token's `azp` check.

One setting (`MKC_CORS_ORIGIN_REGEX`) feeds both checks, so a preview that passes CORS is
never refused by the token verifier (decision 45). Keys are generated at runtime.
"""

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mkc.api.app import create_app
from mkc.config import Settings

ISSUER = "https://example-instance.clerk.accounts.dev"
PRODUCTION = "https://messkonzept-copilot.vercel.app"
PREVIEW_REGEX = r"^https://messkonzept-copilot-[a-z0-9-]+-qamran\.vercel\.app$"

PREVIEWS = [
    "https://messkonzept-copilot-i7324q3rw-qamran.vercel.app",
    "https://messkonzept-copilot-git-mkc-10-cd-qamran.vercel.app",
]
REFUSED = [
    "http://messkonzept-copilot-i7324q3rw-qamran.vercel.app",  # not https
    "https://messkonzept-copilot-i7324q3rw-qamran.vercel.app.evil.example",  # suffix after
    "https://evil-messkonzept-copilot-i7324q3rw-qamran.vercel.app",  # prefix before
    "https://messkonzept-copilot-i7324q3rw-other.vercel.app",  # another team
    "https://messkonzept-copilot-i7324q3rw-qamran.vercel.app:8443",  # another port
    "https://messkonzept-copilot-i7324q3rw-qamran.vercel.app/",  # an origin has no path
    "https://evil.example",
]


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _client(signing_key: rsa.RSAPrivateKey, regex: str = PREVIEW_REGEX) -> TestClient:
    settings = Settings(
        clerk_issuer=ISSUER,
        clerk_authorized_parties=[PRODUCTION],
        cors_origins=[PRODUCTION],
        cors_origin_regex=regex,
    )
    public_key = signing_key.public_key()
    return TestClient(create_app(settings, key_resolver=lambda _token: public_key))


def _token(signing_key: rsa.RSAPrivateKey, azp: str) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": "user_123",
        "iss": ISSUER,
        "azp": azp,
        "iat": now,
        "nbf": now - 5,
        "exp": now + 60,
    }
    return jwt.encode(payload, signing_key, algorithm="RS256")


def _preflight(client: TestClient, origin: str) -> Any:
    return client.options(
        "/api/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def _me(client: TestClient, signing_key: rsa.RSAPrivateKey, azp: str) -> int:
    headers = {"Authorization": f"Bearer {_token(signing_key, azp)}"}
    return client.get("/api/me", headers=headers).status_code


@pytest.mark.parametrize("origin", [PRODUCTION, *PREVIEWS])
def test_allowed_origins_pass_cors(signing_key: rsa.RSAPrivateKey, origin: str) -> None:
    response = _preflight(_client(signing_key), origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", REFUSED)
def test_other_origins_fail_cors(signing_key: rsa.RSAPrivateKey, origin: str) -> None:
    response = _preflight(_client(signing_key), origin)
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("azp", [PRODUCTION, *PREVIEWS])
def test_allowed_origins_pass_azp(signing_key: rsa.RSAPrivateKey, azp: str) -> None:
    assert _me(_client(signing_key), signing_key, azp) == 200


@pytest.mark.parametrize("azp", REFUSED)
def test_other_origins_fail_azp(signing_key: rsa.RSAPrivateKey, azp: str) -> None:
    assert _me(_client(signing_key), signing_key, azp) == 401


@pytest.mark.parametrize("origin", PREVIEWS)
def test_empty_regex_allows_no_preview(signing_key: rsa.RSAPrivateKey, origin: str) -> None:
    client = _client(signing_key, regex="")
    assert "access-control-allow-origin" not in _preflight(client, origin).headers
    assert _me(client, signing_key, origin) == 401


def test_regex_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_CORS_ORIGIN_REGEX", PREVIEW_REGEX)
    assert Settings().cors_origin_regex == PREVIEW_REGEX


def test_regex_defaults_to_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MKC_CORS_ORIGIN_REGEX", raising=False)
    assert Settings().cors_origin_regex == ""


def test_invalid_regex_is_refused_at_start() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origin_regex="^https://(unclosed$")
