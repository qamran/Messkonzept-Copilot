"""MKC-16.5: `save_draft` is idempotent, keyed by the harness's ids (decision 56)."""

from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from mkc.harness.drafts import make_save_draft, record_key
from mkc.harness.registry import default_registry
from mkc.harness.states import ItemState
from mkc.harness.tools import ToolEnv, ToolRegistry
from mkc.models.types import ToolCall
from tests.harness.conftest import make_run
from tests.harness.test_loop import call, start
from tests.harness.test_resume import Crash, CrashingTools, go
from tests.models.fakes import ai, fake

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def env_for(run_id: int, item_id: int, concept_key: str = "MK-1") -> ToolEnv:
    return ToolEnv(run_id, item_id, "sha256:doc", concept_key)


def save(registry: ToolRegistry, env: ToolEnv, body: dict[str, Any]) -> Any:
    return registry.execute(ToolCall(id="s", name="save_draft", args={"draft": body}), "item", env)


def drafts(engine: Engine) -> list[tuple[str, str, int, dict[str, Any]]]:
    query = text("select document_hash, concept_key, item_id, body from draft order by id")
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(query)]  # type: ignore[misc]


def test_save_draft_twice_creates_one_draft(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    registry = default_registry(sessions=sessionmaker(engine))
    first = save(registry, env_for(run_id, item_id), {"lbs": "9992000000026"})
    second = save(registry, env_for(run_id, item_id), {"lbs": "9992000000018"})
    assert first.ok and second.ok
    assert first.data == second.data  # the same draft id
    assert drafts(engine) == [("sha256:doc", "MK-1", item_id, {"lbs": "9992000000018"})]


def test_the_key_comes_from_the_harness_not_the_arguments(engine: Engine) -> None:
    run_id, ids = make_run(engine, "running", "running")
    registry = default_registry(sessions=sessionmaker(engine))
    spoof = {"document_hash": "sha256:other", "concept_key": "MK-1"}
    save(registry, env_for(run_id, ids[0], "MK-1"), spoof)
    save(registry, env_for(run_id, ids[1], "MK-2"), spoof)
    assert [(d[0], d[1], d[2]) for d in drafts(engine)] == [
        ("sha256:doc", "MK-1", ids[0]),
        ("sha256:doc", "MK-2", ids[1]),
    ]


def test_record_key_needs_the_item_ids() -> None:
    assert record_key(ToolEnv(1, 2, "sha256:doc", "MK-1")) == ("sha256:doc", "MK-1")
    with pytest.raises(ValueError, match="document_hash"):
        record_key(ToolEnv(1))


def test_without_sessions_save_draft_stays_the_placeholder() -> None:
    result = save(default_registry(), ToolEnv(1, 2, "sha256:doc", "MK-1"), {})
    assert result.error is not None and result.error.code == "not_implemented"


class DraftTools(CrashingTools):
    """The test tools with the real `save_draft`."""

    def __init__(self, engine: Engine, crash_on: int | None = None) -> None:
        super().__init__(crash_on=crash_on or 0)
        self.save_draft = make_save_draft(sessionmaker(engine))  # type: ignore[method-assign]


def test_a_crash_after_the_draft_write_then_resume_gives_one_draft(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    save_then_read = [call("save_draft", "s1", draft={"v": 1}), call("extract_text", "r1", page=1)]
    with pytest.raises(Crash):  # the draft is written, then the turn dies before its checkpoint
        go(engine, item_id, fake(ai(tool_calls=save_then_read)), DraftTools(engine, crash_on=1))
    assert [d[3] for d in drafts(engine)] == [{"v": 1}]

    again = fake(ai(tool_calls=[call("save_draft", "s2", draft={"v": 2})]))
    assert go(engine, item_id, again, DraftTools(engine)).state is ItemState.DRAFT_SAVED
    assert [d[3] for d in drafts(engine)] == [{"v": 2}]


def test_0007_creates_draft_and_downgrades(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))

    def describe() -> tuple[set[str], set[tuple[str, ...]]]:
        engine = create_engine(database_env)
        try:
            with engine.connect() as conn:
                insp = inspect(conn)
                if not insp.has_table("draft"):
                    return set(), set()
                constraints = insp.get_unique_constraints("draft")
                return (
                    {c["name"] for c in insp.get_columns("draft")},
                    {tuple(u["column_names"]) for u in constraints},
                )
        finally:
            engine.dispose()

    command.upgrade(config, "head")
    columns, unique = describe()
    assert columns == {"id", "document_hash", "concept_key", "item_id", "body", "created_at",
                       "updated_at"}  # fmt: skip
    assert unique == {("document_hash", "concept_key")}
    command.downgrade(config, "0006")
    assert describe() == (set(), set())
    command.upgrade(config, "head")
    assert describe()[0] == columns
