"""Worker test fixtures: the harness DB fixtures, and no database unless a test asks for one.

`mkc.worker.main.run` reads DATABASE_URL. Without `database_env` it points at a closed port,
so these tests never touch the dev database and show the worker runs without one (as in the
kind and Compose smoke tests). `database_env` overrides it for the tests that need a database.
"""

import pytest

from tests.harness.conftest import engine

__all__ = ["engine", "no_database"]

NOWHERE = "postgresql+psycopg://mkc:mkc@127.0.0.1:1/mkc"


@pytest.fixture(autouse=True)
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", NOWHERE)
    monkeypatch.setenv("MKC_DATABASE_CONNECT_TIMEOUT_SECONDS", "2")
