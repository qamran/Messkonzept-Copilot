"""Engine and session handling.

The engine is created on first use, so the API and the worker import without a database.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from mkc.config import Settings, get_settings


def engine_options(settings: Settings) -> dict[str, Any]:
    """Engine options: check pooled connections before use, fail a connect attempt after
    `database_connect_timeout_seconds`, and notice a dead peer through TCP keepalives
    (MKC-17, decision 57)."""
    return {
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": settings.database_connect_timeout_seconds,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    }


@lru_cache(maxsize=4)
def _engine_for(url: str, connect_timeout: int) -> Engine:
    settings = Settings(database_url=url, database_connect_timeout_seconds=connect_timeout)
    return create_engine(url, **engine_options(settings))


def get_engine() -> Engine:
    """The engine for the current DATABASE_URL (one shared engine per URL)."""
    settings = get_settings()
    return _engine_for(settings.database_url, settings.database_connect_timeout_seconds)


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
