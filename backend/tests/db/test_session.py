"""MKC-5.2: get_session() commits on success and rolls back on error."""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from mkc.config import Settings
from mkc.db.session import engine_options, get_engine, get_session


class Boom(Exception):
    pass


@pytest.fixture
def notes(database_env: URL) -> None:
    with get_engine().begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS notes"))
        conn.execute(text("CREATE TABLE notes (body text NOT NULL)"))


def _count() -> int:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT count(*) FROM notes")).scalar_one()


def test_session_commits_on_success(notes: None) -> None:
    with get_session() as session:
        session.execute(text("INSERT INTO notes VALUES ('kept')"))
    assert _count() == 1


def test_session_rolls_back_on_error(notes: None) -> None:
    with pytest.raises(Boom), get_session() as session:
        session.execute(text("INSERT INTO notes VALUES ('lost')"))
        raise Boom
    assert _count() == 0


def test_engine_follows_database_url(database_env: URL) -> None:
    assert get_engine().url.database == database_env.database


# MKC-17.3: a paused or unreachable database fails fast instead of hanging (decision 57).
def test_engine_options_set_a_connect_timeout_and_keepalives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MKC_DATABASE_CONNECT_TIMEOUT_SECONDS", "7")
    options = engine_options(Settings())
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {
        "connect_timeout": 7,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }
