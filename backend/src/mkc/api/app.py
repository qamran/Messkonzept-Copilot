"""FastAPI application factory."""

import logging
from collections.abc import Callable
from importlib.metadata import version
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
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
from mkc.api.backup_status import BackupStatus, LatestRuns, latest_backup_runs, summarize
from mkc.config import Settings, get_settings

log = logging.getLogger("mkc.api")


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

    @app.get("/api/admin/backup-status")
    def backup_status(
        _admin: Annotated[User, Depends(require_admin)],
        load: Annotated[Callable[[], LatestRuns], Depends(latest_backup_runs)],
    ) -> BackupStatus:
        try:
            last_run, last_success = load()
        except Exception as error:
            # Details (host, user) stay in the server log; the client gets a plain 503.
            log.error("backup status unavailable: %s", type(error).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backup status unavailable",
            ) from None
        return summarize(last_run, last_success, settings.backup_stale_hours)

    return app
