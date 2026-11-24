"""FastAPI application factory."""

from importlib.metadata import version

from fastapi import FastAPI
from pydantic import BaseModel

from mkc.config import Settings, get_settings


class Health(BaseModel):
    status: str


class VersionInfo(BaseModel):
    version: str
    commit: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API. Serve with `uvicorn mkc.api.app:create_app --factory`."""
    settings = settings or get_settings()
    app = FastAPI(title="Messkonzept-Copilot", version=version("mkc"))

    @app.get("/health")
    def health() -> Health:
        return Health(status="ok")

    @app.get("/api/version")
    def api_version() -> VersionInfo:
        return VersionInfo(version=version("mkc"), commit=settings.commit)

    return app
