"""MKC-23.3: the approval queue's own rules, beyond the test agent's acceptance tests.

- Migration 0014 creates `approval` (unique `draft_id`) and downgrades.
- `enqueue_approval` queues only the calling item's own draft, by a numeric row id.
- The baseline's in-memory `enqueue_approval` refuses an unknown or another item's entry.
- Only `approved` and `committed` lock a draft: after a rejection the key can be saved again.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text, update
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Item
from mkc.harness.baseline import RunMemory
from mkc.harness.registry import default_registry
from mkc.harness.tools import ToolEnv
from mkc.models.types import ToolCall
from tests.extraction.drafts import valid_draft
from tests.harness.conftest import make_run

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture(autouse=True)
def empty_queue(engine: Engine) -> Iterator[None]:
    with engine.begin() as conn:
        conn.execute(text("truncate approval restart identity cascade"))
    yield


def entries(engine: Engine) -> list[tuple[int, int]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("select draft_id, item_id from approval"))]  # type: ignore[misc]


def run_op(registry: Any, name: str, args: dict[str, Any], env: ToolEnv) -> Any:
    return registry.execute(ToolCall(id="c", name=name, args=args), "run", env)


def saved_draft(engine: Engine) -> tuple[Any, list[int], int]:
    """A registry, two running items of one run, and item 1's saved draft id."""
    run_id, ids = make_run(engine, "running", "running")
    registry = default_registry(sessions=sessionmaker(engine))
    env = ToolEnv(run_id, ids[0], "sha256:doc", "MK-1")
    call = ToolCall(id="s", name="save_draft", args={"draft": valid_draft()})
    result = registry.execute(call, "item", env)
    assert result.ok, result.error
    return registry, ids, int(result.data["draft_id"])


def test_enqueue_approval_upserts_one_row_per_draft(engine: Engine) -> None:
    registry, (first, _), draft_id = saved_draft(engine)
    env = ToolEnv(1, first, "sha256:doc", "MK-1")
    one = run_op(registry, "enqueue_approval", {"draft_id": str(draft_id)}, env)
    two = run_op(registry, "enqueue_approval", {"draft_id": str(draft_id)}, env)
    assert one.ok and two.ok and one.data == two.data
    assert entries(engine) == [(draft_id, first)]


def test_enqueue_approval_refuses_another_items_draft(engine: Engine) -> None:
    registry, (_, second), draft_id = saved_draft(engine)
    env = ToolEnv(1, second, "sha256:doc", "MK-2")
    result = run_op(registry, "enqueue_approval", {"draft_id": str(draft_id)}, env)
    assert result.error is not None and result.error.code == "invalid_args"
    assert entries(engine) == []


@pytest.mark.parametrize("draft_id", ["d-1", "1.0", "-1", "\N{ARABIC-INDIC DIGIT ONE}"])
def test_enqueue_approval_refuses_a_non_numeric_id(engine: Engine, draft_id: str) -> None:
    registry, (first, _), _ = saved_draft(engine)
    env = ToolEnv(1, first, "sha256:doc", "MK-1")
    result = run_op(registry, "enqueue_approval", {"draft_id": draft_id}, env)
    assert result.error is not None and result.error.code == "invalid_args"
    assert entries(engine) == []


def test_memory_enqueue_refuses_unknown_and_foreign_entries() -> None:
    memory = RunMemory(run_id=1)
    registry = default_registry(approvals=memory)
    mine, other = ToolEnv(1, 2, "sha256:doc", "MK-1"), ToolEnv(1, 3, "sha256:doc", "MK-2")
    call = ToolCall(id="s", name="save_draft", args={"draft": valid_draft()})
    draft_id = registry.execute(call, "item", mine).data["draft_id"]
    for bad, env in (("memory-2", mine), ("memory-x", mine), ("7", mine), (draft_id, other)):
        result = run_op(registry, "enqueue_approval", {"draft_id": bad}, env)
        assert result.error is not None and result.error.code == "invalid_args", bad
    assert "queued" not in memory.approvals[0]
    assert run_op(registry, "enqueue_approval", {"draft_id": draft_id}, mine).ok
    assert memory.approvals[0]["queued"] is True


def test_a_rejected_draft_can_be_saved_again(engine: Engine) -> None:
    registry, (first, second), draft_id = saved_draft(engine)
    with Session(engine) as session, session.begin():
        session.execute(update(Item).where(Item.id == first).values(state="rejected"))
    env = ToolEnv(1, second, "sha256:doc", "MK-1")
    call = ToolCall(id="s", name="save_draft", args={"draft": valid_draft("v2")})
    result = registry.execute(call, "item", env)
    assert result.ok, result.error
    assert result.data["draft_id"] == draft_id


def test_0014_creates_approval_and_downgrades(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))

    def describe() -> tuple[set[str], set[tuple[str, ...]]]:
        engine = create_engine(database_env)
        try:
            with engine.connect() as conn:
                insp = inspect(conn)
                if not insp.has_table("approval"):
                    return set(), set()
                unique = {tuple(u["column_names"]) for u in insp.get_unique_constraints("approval")}
                return {c["name"] for c in insp.get_columns("approval")}, unique
        finally:
            engine.dispose()

    command.upgrade(config, "head")
    columns, unique = describe()
    assert columns == {"id", "draft_id", "item_id", "created_at", "updated_at"}
    assert unique == {("draft_id",)}
    command.downgrade(config, "0013")
    assert describe() == (set(), set())
    command.upgrade(config, "head")
    assert describe() == (columns, unique)
