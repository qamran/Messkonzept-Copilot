"""MKC-5.3: Alembic migrations round-trip between base and head."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _state(url: URL) -> tuple[bool, bool]:
    """(vector extension installed, alembic_version table present)."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            has_vector = conn.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one()
            has_version = inspect(conn).has_table("alembic_version") and bool(
                conn.execute(text("SELECT count(*) FROM alembic_version")).scalar_one()
            )
        return bool(has_vector), has_version
    finally:
        engine.dispose()


def test_upgrade_downgrade_roundtrip(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))

    command.upgrade(config, "head")
    assert _state(database_env) == (True, True)

    command.downgrade(config, "base")
    assert _state(database_env) == (False, False)

    command.upgrade(config, "head")
    assert _state(database_env) == (True, True)
