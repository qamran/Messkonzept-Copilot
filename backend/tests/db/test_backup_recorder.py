"""MKC-11.2: the database recorder writes one backup_runs row per run."""

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from mkc.backup import DbRecorder

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
START = datetime(2026, 11, 26, 2, 30, tzinfo=UTC)
END = datetime(2026, 11, 26, 2, 31, tzinfo=UTC)


def test_start_and_finish_write_one_row(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    engine = create_engine(database_env)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM backup_runs"))
        recorder = DbRecorder(engine)

        run_id = recorder.start(START)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT state FROM backup_runs")).scalar_one() == "running"

        recorder.finish(
            run_id,
            state="ok",
            finished_at=END,
            object_name="nightly/mkc-20261126T023000Z.sql.gz",
            size_bytes=1234,
            error=None,
        )
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT state, started_at, finished_at, object_name, size_bytes"
                    " FROM backup_runs"
                )
            ).one()
        assert row == ("ok", START, END, "nightly/mkc-20261126T023000Z.sql.gz", 1234)
    finally:
        engine.dispose()
