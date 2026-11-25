"""Clerk session-token check (MKC-7.1).

Tokens are verified with the Clerk instance's public keys (JWKS), so no Clerk secret key is
needed. Admin rights come from the custom `role` claim, which the Clerk session token takes from
the user's public metadata (`{"role": "admin"}`, set only in the Clerk dashboard).
"""

from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

ADMIN_ROLE = "admin"
ALGORITHMS = ["RS256"]
LEEWAY_SECONDS = 5
"""Allowed clock skew for `exp` and `nbf`; Clerk tokens live 60 seconds."""

KeyResolver = Callable[[str], Any]
"""Returns the public key that should have signed the given token."""


class User(BaseModel):
    id: str
    role: str | None
    is_admin: bool


class TokenVerifier:
    """Checks signature (RS256 only), expiry, not-before, issuer, subject and authorized party."""

    def __init__(
        self, issuer: str, authorized_parties: list[str], key_resolver: KeyResolver
    ) -> None:
        self._issuer = issuer
        self._authorized_parties = set(authorized_parties)
        self._key_resolver = key_resolver

    def verify(self, token: str) -> User:
        """Return the user for a valid token; raise `jwt.InvalidTokenError` otherwise."""
        claims = jwt.decode(
            token,
            self._key_resolver(token),
            algorithms=ALGORITHMS,
            issuer=self._issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "nbf", "iss", "sub"]},
        )
        # Clerk omits azp when the request had no Origin header; when present it must match.
        azp = claims.get("azp")
        if azp is not None and azp not in self._authorized_parties:
            raise jwt.InvalidTokenError("authorized party not allowed")
        role = claims.get("role") or None
        return User(id=claims["sub"], role=role, is_admin=role == ADMIN_ROLE)


def jwks_url(issuer: str) -> str:
    """Public keys of a Clerk instance."""
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


def jwks_key_resolver(issuer: str) -> KeyResolver:
    """Fetch (and cache) the signing key for a token's `kid` from the instance's JWKS."""
    client = jwt.PyJWKClient(jwks_url(issuer), cache_keys=True)

    def resolve(token: str) -> Any:
        return client.get_signing_key_from_jwt(token).key

    return resolve


_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in or token invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """FastAPI dependency: the signed-in user, or 401. 503 if Clerk is not configured."""
    verifier: TokenVerifier | None = request.app.state.token_verifier
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Login is not configured"
        )
    if credentials is None:
        raise _unauthorized()
    try:
        return verifier.verify(credentials.credentials)
    except jwt.PyJWTError as error:  # includes JWKS lookup errors
        raise _unauthorized() from error


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    """FastAPI dependency: the signed-in admin, or 403 for other signed-in users."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
