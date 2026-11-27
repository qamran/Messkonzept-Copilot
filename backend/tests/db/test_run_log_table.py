"""MKC-19.2: migration 0010 adds `run.trace_id` and the `run_log` table (decision 59)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
RUN_LOG_COLUMNS = {
    "id",
    "run_id",
    "item_id",
    "step",
    "kind",
    "name",
    "ok",
    "error",
    "mode",
    "input_tokens",
    "output_tokens",
    "cost_eur",
    "latency_ms",
    "detail",
    "created_at",
}


def _describe(url: URL) -> dict[str, object]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            run = {c["name"] for c in insp.get_columns("run")}
            if not insp.has_table("run_log"):
                return {"run": run, "run_log": None}
            return {
                "run": run,
                "run_log": {c["name"] for c in insp.get_columns("run_log")},
                "fks": insp.get_foreign_keys("run_log"),
                "indexes": {tuple(i["column_names"]) for i in insp.get_indexes("run_log")},
            }
    finally:
        engine.dispose()


def test_0010_adds_trace_id_and_run_log(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    found = _describe(database_env)
    assert "trace_id" in found["run"]  # type: ignore[operator]
    assert found["run_log"] == RUN_LOG_COLUMNS
    # no foreign keys: a log insert must never wait for the run row lock of `fence`
    assert found["fks"] == []
    assert ("run_id", "id") in found["indexes"]  # type: ignore[operator]


def test_0010_downgrades_and_upgrades_again(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")
    command.downgrade(config, "0009")
    found = _describe(database_env)
    assert "trace_id" not in found["run"]  # type: ignore[operator]
    assert found["run_log"] is None
    command.upgrade(config, "head")
    assert _describe(database_env)["run_log"] == RUN_LOG_COLUMNS
