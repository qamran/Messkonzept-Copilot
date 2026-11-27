"""Settings from environment variables (prefix MKC_)."""

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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

    worker_lease_seconds: float = Field(default=120.0, gt=0)
    """How long a claimed run stays leased without a renewal (MKC-17, decision 57). A crashed
    worker's run is taken over after at most this long."""

    worker_lease_renew_seconds: float = Field(default=20.0, gt=0)
    """How often the lease thread renews the lease; three renewals must fit into a lease."""

    worker_db_backoff_max_seconds: float = Field(default=30.0, gt=0)
    """While the database is unreachable, the worker probes it after 1, 2, 4 … seconds, at
    most this long apart (MKC-17, decision 57)."""

    database_connect_timeout_seconds: int = Field(default=10, ge=1)
    """A connection attempt fails after this long, so a paused database does not hang the
    worker (MKC-17)."""

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

    item_max_steps: int = Field(default=12, ge=1)
    """Model calls one item may make before it fails with `step_limit` (MKC-15, decision 58)."""

    run_max_steps: int = Field(default=300, ge=1)
    """Model calls (stored turns) one run may make before it stops with `run_step_limit`."""

    run_max_wall_seconds: float = Field(default=7200.0, gt=0)
    """Seconds from the run's start (database clock) until it stops with `wall_time`."""

    run_max_cost_eur: Decimal = Field(default=Decimal("3.00"), gt=0)
    """EUR one run may spend (sum of its turns) before it stops with `cost_limit`."""

    tool_max_retries: int = Field(default=3, ge=0)
    """Failed calls of one tool an item may retry; one more fails it with `tool_retries`."""

    model_max_retries: int = Field(default=4, ge=0)
    """Retries of a model call after a transient error (429, 5xx, timeout); then the run stops
    with `model_unavailable`."""

    model_backoff_base_seconds: float = Field(default=2.0, gt=0)
    """First wait before a retry; it doubles per retry (or `Retry-After`, if longer)."""

    model_backoff_max_seconds: float = Field(default=60.0, gt=0)
    """The longest wait between two attempts of a model call."""

    turn_timeout_seconds: float = Field(default=180.0, gt=0)
    """Wall-clock deadline of one model call; after it the call counts as a timeout."""

    item_max_resumes: int = Field(default=3, ge=0)
    """Resumes of an item without a new stored turn; one more fails it with `resume_limit`."""

    turn_inline_max_bytes: int = Field(default=16384, ge=1)
    """A tool result whose JSON is larger is stored as a blob ref, not inline in the turn row
    (MKC-16.2, decision 56). Same default as `mkc.harness.checkpoint.INLINE_MAX_BYTES`."""

    openrouter_api_key: SecretStr = SecretStr("")
    """OpenRouter key (default route, zero data retention). A secret: never logged."""

    google_api_key: SecretStr = SecretStr("")
    """Gemini API key (free tier: public and synthetic input only). A secret."""

    anthropic_api_key: SecretStr = SecretStr("")
    """Anthropic API key. A secret."""

    meta_api_key: SecretStr = SecretStr("")
    """Meta API key (api.meta.ai, Muse models). A secret."""

    langfuse_public_key: str = ""
    """Langfuse project key (`pk-lf-...`). Empty: no Langfuse; `run_log` still records every
    traced event (MKC-19, decision 59)."""

    langfuse_secret_key: SecretStr = SecretStr("")
    """Langfuse secret key (`sk-lf-...`). A secret: never logged."""

    langfuse_base_url: str = "https://cloud.langfuse.com"
    """The Langfuse host of the project's region."""

    langfuse_environment: str = Field(default="development", pattern=r"^[a-z0-9_-]{1,40}$")
    """Langfuse `environment` of every trace (`production` on the VM)."""

    langfuse_timeout_seconds: int = Field(default=5, ge=1, le=60)
    """Timeout of one export to Langfuse; bounds `flush` after a run and on shutdown."""

    @model_validator(mode="after")
    def _lease_outlives_renewals(self) -> "Settings":
        """A lease must survive two missed renewals, or a slow database loses it."""
        if self.worker_lease_renew_seconds * 3 > self.worker_lease_seconds:
            raise ValueError(
                "three renewals must fit into one lease: MKC_WORKER_LEASE_RENEW_SECONDS * 3 "
                "> MKC_WORKER_LEASE_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def _backoff_cap_covers_the_base(self) -> "Settings":
        if self.model_backoff_max_seconds < self.model_backoff_base_seconds:
            raise ValueError(
                "MKC_MODEL_BACKOFF_MAX_SECONDS must be at least MKC_MODEL_BACKOFF_BASE_SECONDS"
            )
        return self

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
