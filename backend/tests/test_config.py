"""MKC-5.2: the database URL setting. MKC-6.2: empty variables mean "unset"."""

from pathlib import Path

import pytest

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
