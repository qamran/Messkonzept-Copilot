"""MKC-11.3: the status query returns the latest run and the latest successful run."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from mkc.api.backup_status import load_latest

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
T0 = datetime(2026, 11, 26, 2, 30, tzinfo=UTC)


def test_latest_run_and_latest_success(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    engine = create_engine(database_env)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM backup_runs"))
        assert load_latest(engine) == (None, None)
        with engine.begin() as conn:
            for day, state in [(0, "ok"), (1, "ok"), (2, "failed")]:
                conn.execute(
                    text(
                        "INSERT INTO backup_runs (started_at, finished_at, state, object_name)"
                        " VALUES (:s, :f, :state, :name)"
                    ),
                    {
                        "s": T0 + timedelta(days=day),
                        "f": T0 + timedelta(days=day, minutes=1),
                        "state": state,
                        "name": f"nightly/day{day}.sql.gz" if state == "ok" else None,
                    },
                )
        last_run, last_success = load_latest(engine)
        assert last_run is not None and last_run.state == "failed"
        assert last_success is not None and last_success.object_name == "nightly/day1.sql.gz"
    finally:
        engine.dispose()
