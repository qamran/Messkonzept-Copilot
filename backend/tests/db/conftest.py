"""Postgres fixtures: every test session runs in a throwaway database.

The database in DATABASE_URL (default: the `docker compose up db` service) is only used to
create and drop a database named `mkc_test_<random>`. Dev data and Supabase are never touched.
If Postgres is unreachable the DB tests fail; set MKC_SKIP_DB_TESTS=1 to skip them on purpose.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from mkc.config import Settings


@pytest.fixture(scope="session")
def db_url() -> Iterator[URL]:
    """URL of a fresh, empty database that is dropped after the test session."""
    if os.environ.get("MKC_SKIP_DB_TESTS") == "1":
        pytest.skip("MKC_SKIP_DB_TESTS=1")
    server = make_url(Settings().database_url)
    name = f"mkc_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as exc:
        admin.dispose()
        pytest.fail(
            f"Postgres not reachable at {server.render_as_string(hide_password=True)}: "
            f"start it with `docker compose up -d db` or set MKC_SKIP_DB_TESTS=1 ({exc})"
        )
    try:
        yield server.set(database=name)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def database_env(db_url: URL, monkeypatch: pytest.MonkeyPatch) -> URL:
    """Point DATABASE_URL at the throwaway database for one test."""
    monkeypatch.setenv("DATABASE_URL", db_url.render_as_string(hide_password=False))
    return db_url
