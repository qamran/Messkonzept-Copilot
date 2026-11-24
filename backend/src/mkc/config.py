"""Settings from environment variables (prefix MKC_)."""

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PSYCOPG_SCHEME = "postgresql+psycopg://"
_BARE_SCHEMES = ("postgres://", "postgresql://")


class Settings(BaseSettings):
    """Runtime settings. Every field can be set with an MKC_<NAME> environment variable."""

    model_config = SettingsConfigDict(env_prefix="MKC_")

    commit: str = "dev"
    """Git commit of the running build; set by CI/CD."""

    worker_poll_seconds: float = 1.0
    """How long the worker waits between polls for work."""

    database_url: str = Field(
        default=f"{_PSYCOPG_SCHEME}mkc:mkc@127.0.0.1:5433/mkc",
        validation_alias=AliasChoices("DATABASE_URL", "MKC_DATABASE_URL"),
    )
    """SQLAlchemy URL from DATABASE_URL. Defaults to the `docker compose up db` service."""

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
