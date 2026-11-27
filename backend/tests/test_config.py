"""MKC-5.2: the database URL setting. MKC-6.2: empty variables mean "unset"."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from mkc.config import Settings


def test_database_url_defaults_to_compose_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MKC_DATABASE_URL", raising=False)
    assert Settings().database_url == "postgresql+psycopg://mkc:mkc@127.0.0.1:5433/mkc"


def test_database_url_read_from_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:5432/x")
    assert Settings().database_url == "postgresql+psycopg://u:p@db.example:5432/x"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_database_url_scheme_mapped_to_psycopg3(
    monkeypatch: pytest.MonkeyPatch, scheme: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://u:p%40ss@db.example:5432/x")
    assert Settings().database_url == "postgresql+psycopg://u:p%40ss@db.example:5432/x"


# MKC-6.2 (PR #86 review): .env.example ships every variable empty, so empty means "unset".
DEFAULT_URL = "postgresql+psycopg://mkc:mkc@127.0.0.1:5433/mkc"
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_empty_variables_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "MKC_DATABASE_URL", "MKC_COMMIT", "MKC_WORKER_POLL_SECONDS"):
        monkeypatch.setenv(name, "")
    settings = Settings()
    assert settings.database_url == DEFAULT_URL
    assert settings.commit == "dev"
    assert settings.worker_poll_seconds == 1.0


def test_env_example_as_is_gives_the_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    pairs = [line.split("=", 1) for line in lines if line.strip() and not line.startswith("#")]
    assert pairs, ".env.example lists no variables"
    for name, value in pairs:
        monkeypatch.setenv(name.strip(), value)
    settings = Settings()
    assert settings.database_url == DEFAULT_URL
    assert settings.commit == "dev"
    assert settings.worker_poll_seconds == 1.0


# MKC-7.1: Clerk and CORS settings.
LOCAL_VITE = ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_clerk_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MKC_CLERK_ISSUER", "MKC_CLERK_AUTHORIZED_PARTIES", "MKC_CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.clerk_issuer == ""
    assert settings.clerk_authorized_parties == LOCAL_VITE
    assert settings.cors_origins == LOCAL_VITE


def test_origin_lists_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_CLERK_AUTHORIZED_PARTIES", "https://a.example, https://b.example")
    monkeypatch.setenv("MKC_CORS_ORIGINS", "https://a.example")
    settings = Settings()
    assert settings.clerk_authorized_parties == ["https://a.example", "https://b.example"]
    assert settings.cors_origins == ["https://a.example"]


def test_clerk_issuer_trailing_slash_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_CLERK_ISSUER", "https://x.clerk.accounts.dev/")
    assert Settings().clerk_issuer == "https://x.clerk.accounts.dev"


def test_item_max_steps_defaults_to_12_and_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MKC_ITEM_MAX_STEPS", raising=False)
    assert Settings().item_max_steps == 12
    monkeypatch.setenv("MKC_ITEM_MAX_STEPS", "5")
    assert Settings().item_max_steps == 5
    monkeypatch.setenv("MKC_ITEM_MAX_STEPS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_turn_inline_max_bytes_defaults_to_16384_and_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mkc.harness.checkpoint import INLINE_MAX_BYTES

    monkeypatch.delenv("MKC_TURN_INLINE_MAX_BYTES", raising=False)
    assert Settings().turn_inline_max_bytes == INLINE_MAX_BYTES == 16384
    monkeypatch.setenv("MKC_TURN_INLINE_MAX_BYTES", "1024")
    assert Settings().turn_inline_max_bytes == 1024
    monkeypatch.setenv("MKC_TURN_INLINE_MAX_BYTES", "0")
    with pytest.raises(ValidationError):
        Settings()


# MKC-17.2: lease timings (decision 57).
def test_lease_timings_default_and_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (Settings().worker_lease_seconds, Settings().worker_lease_renew_seconds) == (120, 20)
    monkeypatch.setenv("MKC_WORKER_LEASE_SECONDS", "90")
    monkeypatch.setenv("MKC_WORKER_LEASE_RENEW_SECONDS", "30")
    assert (Settings().worker_lease_seconds, Settings().worker_lease_renew_seconds) == (90, 30)


@pytest.mark.parametrize(("lease", "renew"), [(60, 21), (60, 0), (0, 0)])
def test_three_renewals_must_fit_into_one_lease(lease: float, renew: float) -> None:
    with pytest.raises(ValidationError, match=r"three renewals|greater than 0"):
        Settings(worker_lease_seconds=lease, worker_lease_renew_seconds=renew)
