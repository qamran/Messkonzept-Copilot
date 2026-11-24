"""MKC-5.2: the database URL setting."""

import pytest

from mkc.config import Settings


def test_database_url_defaults_to_compose_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MKC_DATABASE_URL", raising=False)
    assert Settings().database_url == "postgresql+psycopg://mkc:mkc@localhost:5433/mkc"


def test_database_url_read_from_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:5432/x")
    assert Settings().database_url == "postgresql+psycopg://u:p@db.example:5432/x"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_database_url_scheme_mapped_to_psycopg3(
    monkeypatch: pytest.MonkeyPatch, scheme: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://u:p%40ss@db.example:5432/x")
    assert Settings().database_url == "postgresql+psycopg://u:p%40ss@db.example:5432/x"
