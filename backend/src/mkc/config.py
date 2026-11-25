"""Settings from environment variables (prefix MKC_)."""

from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_PSYCOPG_SCHEME = "postgresql+psycopg://"
_BARE_SCHEMES = ("postgres://", "postgresql://")
_LOCAL_VITE = ["http://localhost:5173", "http://127.0.0.1:5173"]

OriginList = Annotated[list[str], NoDecode]
"""A list read from one comma-separated environment variable."""


class Settings(BaseSettings):
    """Runtime settings. Every field can be set with an MKC_<NAME> environment variable."""

    # env_ignore_empty: an empty variable (as in .env.example) means "use the default".
    model_config = SettingsConfigDict(env_prefix="MKC_", env_ignore_empty=True)

    commit: str = "dev"
    """Git commit of the running build; set by CI/CD."""

    worker_poll_seconds: float = 1.0
    """How long the worker waits between polls for work."""

    worker_heartbeat_file: str = ""
    """File the worker touches on start and every poll. Empty = off (the Helm chart sets it)."""

    worker_heartbeat_max_age_seconds: float = 30.0
    """`mkc-worker-health` fails when the heartbeat is older than this."""

    database_url: str = Field(
        default=f"{_PSYCOPG_SCHEME}mkc:mkc@127.0.0.1:5433/mkc",
        validation_alias=AliasChoices("DATABASE_URL", "MKC_DATABASE_URL"),
    )
    """SQLAlchemy URL from DATABASE_URL. Defaults to the `docker compose up db` service."""

    clerk_issuer: str = ""
    """Clerk instance (Frontend API URL). Empty = auth not configured; protected routes give 503."""

    clerk_authorized_parties: OriginList = Field(default_factory=lambda: list(_LOCAL_VITE))
    """Origins allowed in a token's `azp` claim (comma-separated)."""

    cors_origins: OriginList = Field(default_factory=lambda: list(_LOCAL_VITE))
    """Browser origins allowed to call the API (comma-separated)."""

    @field_validator("clerk_authorized_parties", "cors_origins", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("clerk_issuer")
    @classmethod
    def _strip_trailing_slash(cls, issuer: str) -> str:
        return issuer.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3(cls, url: str) -> str:
        """Map bare Postgres schemes (as Supabase hands them out) to the psycopg 3 driver."""
        for scheme in _BARE_SCHEMES:
            if url.startswith(scheme):
                return _PSYCOPG_SCHEME + url.removeprefix(scheme)
        return url


def get_settings() -> Settings:
    """Build settings from the current environment."""
    return Settings()
