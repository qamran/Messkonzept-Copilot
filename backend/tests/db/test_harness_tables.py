"""MKC-15.3: tables `run`, `item` and `turn` (migration 0004)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
TABLES = {"run", "item", "turn"}
COLUMNS = {
    "run": {"id", "state", "stop_reason", "created_at", "updated_at"},
    "item": {
        "id",
        "run_id",
        "concept_key",
        "document_hash",
        "task",
        "state",
        "failure_reason",
        "created_at",
        "updated_at",
    },
    "turn": {"id", "item_id", "number", "assistant", "tool_results", "cost_eur", "created_at"},
}


def _describe(url: URL) -> dict[str, dict[str, object]]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            return {
                name: {
                    "columns": {c["name"] for c in insp.get_columns(name)},
                    "unique": {tuple(u["column_names"]) for u in insp.get_unique_constraints(name)},
                    "fks": {
                        (tuple(f["constrained_columns"]), f["referred_table"])
                        for f in insp.get_foreign_keys(name)
                    },
                }
                for name in TABLES
                if insp.has_table(name)
            }
    finally:
        engine.dispose()


def test_0004_creates_the_harness_tables(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    tables = _describe(database_env)
    assert set(tables) == TABLES
    for name, columns in COLUMNS.items():
        assert tables[name]["columns"] == columns, name
    assert ("run_id", "concept_key") in tables["item"]["unique"]  # type: ignore[operator]
    assert ("item_id", "number") in tables["turn"]["unique"]  # type: ignore[operator]
    assert tables["item"]["fks"] == {(("run_id",), "run")}
    assert tables["turn"]["fks"] == {(("item_id",), "item")}


def test_0004_downgrades_and_upgrades_again(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")
    command.downgrade(config, "0003")
    assert _describe(database_env) == {}
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # the deploy hook runs it on every release
    assert set(_describe(database_env)) == TABLES
