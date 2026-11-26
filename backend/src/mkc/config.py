"""Settings from environment variables (prefix MKC_)."""

import re
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
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

    cors_origin_regex: str = ""
    """Extra origins as one regular expression (full match), for Vercel previews. Used by CORS
    and by the token's `azp` check alike. Empty = off."""

    backup_upload_url: SecretStr = SecretStr("")
    """Object Storage pre-authenticated request that can only write objects (decision 49).
    A secret: it is never logged. The object name is appended to it. Empty = backups fail."""

    backup_dir: str = "/tmp/backup"
    """Work directory for the dump before the upload (an emptyDir in the CronJob)."""

    backup_allow_http: bool = False
    """Allow a plain http upload link: only for the tests and the Compose smoke stub."""

    backup_stale_hours: float = 26.0
    """`/api/admin/backup-status` reports `stale` when the last good backup is older."""

    model_mode: Literal["live", "record", "replay"] = "replay"
    """`live` calls providers; `record` calls them and stores the replies; `replay` (default, so
    nothing spends money by accident) only reads stored replies and needs no API key."""

    models_file: str = ""
    """Role → model mapping and prices. Empty = the packaged `mkc/models/models.yaml`."""

    model_replay_dir: str = ""
    """Directory of recorded replies; required in `record` and `replay` mode."""

    openrouter_api_key: SecretStr = SecretStr("")
    """OpenRouter key (default route, zero data retention). A secret: never logged."""

    google_api_key: SecretStr = SecretStr("")
    """Gemini API key (free tier: public and synthetic input only). A secret."""

    anthropic_api_key: SecretStr = SecretStr("")
    """Anthropic API key. A secret."""

    meta_api_key: SecretStr = SecretStr("")
    """Meta API key (api.meta.ai, Muse models). A secret."""

    @field_validator("clerk_authorized_parties", "cors_origins", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_origin_regex")
    @classmethod
    def _compiles(cls, pattern: str) -> str:
        """A broken pattern stops the app at start instead of failing per request."""
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"MKC_CORS_ORIGIN_REGEX is not a valid regex: {error}") from error
        return pattern

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
