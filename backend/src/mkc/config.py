"""Settings from environment variables (prefix MKC_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Every field can be set with an MKC_<NAME> environment variable."""

    model_config = SettingsConfigDict(env_prefix="MKC_")

    commit: str = "dev"
    """Git commit of the running build; set by CI/CD."""

    worker_poll_seconds: float = 1.0
    """How long the worker waits between polls for work."""


def get_settings() -> Settings:
    """Build settings from the current environment."""
    return Settings()
