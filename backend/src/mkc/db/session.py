"""Engine and session handling.

The engine is created on first use, so the API and the worker import without a database.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from mkc.config import get_settings


@lru_cache(maxsize=4)
def _engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    """The engine for the current DATABASE_URL (one shared engine per URL)."""
    return _engine_for(get_settings().database_url)


@contextmanager
def get_session() -> Iterator[Session]:
    """A session that commits on success, rolls back on error and is always closed."""
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
