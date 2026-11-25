"""FastAPI application factory."""

from importlib.metadata import version
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mkc.api.auth import (
    KeyResolver,
    TokenVerifier,
    User,
    jwks_key_resolver,
    require_admin,
    require_user,
)
from mkc.config import Settings, get_settings


class Health(BaseModel):
    status: str


class VersionInfo(BaseModel):
    version: str
    commit: str


def create_app(
    settings: Settings | None = None, key_resolver: KeyResolver | None = None
) -> FastAPI:
    """Build the API. Serve with `uvicorn mkc.api.app:create_app --factory`.

    `key_resolver` replaces the JWKS lookup (tests sign their own tokens).
    """
    settings = settings or get_settings()
    app = FastAPI(title="Messkonzept-Copilot", version=version("mkc"))
    app.state.token_verifier = (
        TokenVerifier(
            settings.clerk_issuer,
            settings.clerk_authorized_parties,
            key_resolver or jwks_key_resolver(settings.clerk_issuer),
            settings.cors_origin_regex,
        )
        if settings.clerk_issuer
        else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # The same pattern as the azp check (decision 45); Starlette uses a full match.
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health")
    def health() -> Health:
        return Health(status="ok")

    @app.get("/api/version")
    def api_version() -> VersionInfo:
        return VersionInfo(version=version("mkc"), commit=settings.commit)

    @app.get("/api/me")
    def me(user: Annotated[User, Depends(require_user)]) -> User:
        return user

    @app.get("/api/admin/ping")
    def admin_ping(_admin: Annotated[User, Depends(require_admin)]) -> Health:
        return Health(status="ok")

    return app
