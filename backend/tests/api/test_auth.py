"""MKC-7.1: Clerk session tokens are verified with public keys; admin comes from the role claim.

Every key pair is generated at runtime, so no key is committed and no test touches the network.
"""

import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from mkc.api.app import create_app
from mkc.api.auth import jwks_url
from mkc.config import Settings

ISSUER = "https://example-instance.clerk.accounts.dev"
ORIGIN = "http://localhost:5173"

TokenFactory = Callable[..., str]


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def other_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def make_token(signing_key: rsa.RSAPrivateKey) -> TokenFactory:
    def factory(
        key: Any = None,
        algorithm: str = "RS256",
        headers: dict[str, Any] | None = None,
        **claims: Any,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": "user_123",
            "iss": ISSUER,
            "azp": ORIGIN,
            "iat": now,
            "nbf": now - 5,
            "exp": now + 60,
            "role": "",
        }
        payload.update(claims)
        payload = {k: v for k, v in payload.items() if v is not None}
        return jwt.encode(
            payload, key if key is not None else signing_key, algorithm=algorithm, headers=headers
        )

    return factory


@pytest.fixture
def client(signing_key: rsa.RSAPrivateKey) -> TestClient:
    settings = Settings(clerk_issuer=ISSUER, clerk_authorized_parties=[ORIGIN])
    public_key = signing_key.public_key()
    return TestClient(create_app(settings, key_resolver=lambda _token: public_key))


def _get(client: TestClient, path: str, token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.get(path, headers=headers)


def test_me_returns_the_user(client: TestClient, make_token: TokenFactory) -> None:
    response = _get(client, "/api/me", make_token())
    assert response.status_code == 200
    assert response.json() == {"id": "user_123", "role": None, "is_admin": False}


def test_me_for_an_admin(client: TestClient, make_token: TokenFactory) -> None:
    response = _get(client, "/api/me", make_token(role="admin"))
    assert response.json() == {"id": "user_123", "role": "admin", "is_admin": True}


def test_missing_header_is_401(client: TestClient) -> None:
    response = _get(client, "/api/me", None)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer not-a-jwt"])
def test_malformed_header_is_401(client: TestClient, header: str) -> None:
    assert client.get("/api/me", headers={"Authorization": header}).status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"exp": int(time.time()) - 120}, id="expired"),
        pytest.param({"nbf": int(time.time()) + 120}, id="not-yet-valid"),
        pytest.param({"iss": "https://other.clerk.accounts.dev"}, id="wrong-issuer"),
        pytest.param({"iss": None}, id="no-issuer"),
        pytest.param({"exp": None}, id="no-expiry"),
        pytest.param({"sub": None}, id="no-subject"),
        pytest.param({"azp": "https://evil.example"}, id="wrong-azp"),
    ],
)
def test_invalid_claims_are_401(
    client: TestClient, make_token: TokenFactory, claims: dict[str, Any]
) -> None:
    assert _get(client, "/api/me", make_token(**claims)).status_code == 401


def test_token_without_azp_is_accepted(client: TestClient, make_token: TokenFactory) -> None:
    # Clerk omits azp when the request had no Origin header (Clerk session-token docs).
    assert _get(client, "/api/me", make_token(azp=None)).status_code == 200


def test_wrong_signing_key_is_401(
    client: TestClient, make_token: TokenFactory, other_key: rsa.RSAPrivateKey
) -> None:
    assert _get(client, "/api/me", make_token(key=other_key)).status_code == 401


def test_hs256_token_is_401(client: TestClient, make_token: TokenFactory) -> None:
    token = make_token(key="a-shared-secret-of-at-least-32-bytes!!", algorithm="HS256")
    assert _get(client, "/api/me", token).status_code == 401


def test_unsigned_token_is_401(client: TestClient, make_token: TokenFactory) -> None:
    assert _get(client, "/api/me", make_token(key="", algorithm="none")).status_code == 401


def test_admin_route_rejects_a_normal_user(client: TestClient, make_token: TokenFactory) -> None:
    response = _get(client, "/api/admin/ping", make_token(role="member"))
    assert response.status_code == 403


def test_admin_route_allows_an_admin(client: TestClient, make_token: TokenFactory) -> None:
    response = _get(client, "/api/admin/ping", make_token(role="admin"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_admin_route_needs_a_token(client: TestClient) -> None:
    assert _get(client, "/api/admin/ping", None).status_code == 401


def test_auth_not_configured_is_503(make_token: TokenFactory) -> None:
    client = TestClient(create_app(Settings(clerk_issuer="")))
    assert _get(client, "/api/me", make_token()).status_code == 503


def test_public_routes_need_no_token() -> None:
    client = TestClient(create_app(Settings(clerk_issuer="")))
    assert client.get("/health").status_code == 200
    assert client.get("/api/version").status_code == 200


def test_jwks_url_is_derived_from_the_issuer() -> None:
    assert jwks_url(ISSUER + "/") == f"{ISSUER}/.well-known/jwks.json"


def test_cors_allows_the_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/api/me",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_cors_rejects_other_origins(client: TestClient) -> None:
    response = client.options(
        "/api/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers
