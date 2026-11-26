"""MKC-11.1: migration 0002 adds `backup_runs`; the models match the migrations."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from mkc.db.base import Base

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

COLUMNS = {
    "id",
    "started_at",
    "finished_at",
    "state",
    "object_name",
    "size_bytes",
    "error",
}


def _columns(url: URL) -> set[str] | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            if not insp.has_table("backup_runs"):
                return None
            return {c["name"] for c in insp.get_columns("backup_runs")}
    finally:
        engine.dispose()


def test_0002_creates_backup_runs_and_downgrades(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))

    command.upgrade(config, "head")
    assert _columns(database_env) == COLUMNS

    command.downgrade(config, "0001")
    assert _columns(database_env) is None

    command.upgrade(config, "head")
    # A second upgrade is a no-op (the deploy hook runs it on every release).
    command.upgrade(config, "head")
    assert _columns(database_env) == COLUMNS


def test_models_match_migrations(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    import mkc.db.models  # noqa: F401  (registers the tables on Base.metadata)

    engine = create_engine(database_env)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    assert diff == []
