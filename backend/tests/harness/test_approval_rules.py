"""MKC-23 mutation pass: rules of the harness's enqueue path the acceptance tests left open.

- A later run's enqueue points the one `approval` row at the newest item (survivor D9).
- The crash-window sweep queues only its own run's items (L8), and is fenced: a worker that
  loses its lease mid-sweep queues nothing and moves no state (L10, L11).
- A failed `enqueue_approval` leaves the item `draft_saved`, durably (L12) and in the
  baseline's memory (L15).
- The baseline queues the item's last save of the turn (B2); `memory-0` is no entry (B5).
"""

from collections.abc import Callable, Iterator
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Draft
from mkc.harness.baseline import RunMemory
from mkc.harness.limits import Limits
from mkc.harness.loop import process_run
from mkc.harness.mode import SWITCHES, HarnessMode
from mkc.harness.registry import default_registry
from mkc.harness.tools import ToolEnv, ToolRegistry
from mkc.models.types import ToolCall
from mkc.worker.lease import LeaseLost
from tests.extraction.drafts import valid_draft
from tests.harness.conftest import states
from tests.harness.test_approvals import item_row, queue_entries, saves, set_state
from tests.harness.test_baseline import go, make
from tests.harness.test_loop import call, client_for
from tests.models.fakes import FakeChatModel, ai


@pytest.fixture(autouse=True)
def empty_queue(engine: Engine) -> Iterator[None]:
    with engine.begin() as conn:
        conn.execute(text("truncate approval restart identity cascade"))
    yield


def crash_window(engine: Engine) -> tuple[int, int]:
    """A full run whose item is `draft_saved` with its draft row and no queue row."""
    run_id, (item_id,) = make(engine, 1, mode="full")
    set_state(engine, item_id, "draft_saved")
    with Session(engine) as session, session.begin():
        session.add(Draft(document_hash="sha256:doc", concept_key="MK-1", item_id=item_id,
                          body=valid_draft()))  # fmt: skip
    return run_id, item_id


def fails_from(n: int) -> Callable[[Session], None]:
    """A fence that passes n - 1 times, then raises like a lost lease."""
    calls = [0]

    def fence(session: Session) -> None:
        calls[0] += 1
        if calls[0] >= n:
            raise LeaseLost("lease taken over (test)")

    return fence


def with_enqueue(registry: ToolRegistry, fn: Any) -> ToolRegistry:
    run = [replace(t, fn=fn) if t.name == "enqueue_approval" else t
           for t in registry.for_context("run")]  # fmt: skip
    return ToolRegistry(item=registry.for_context("item"), run=run)


def broken(args: Any, env: ToolEnv) -> Any:
    raise RuntimeError("queue unavailable (test)")


def queued_items(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("select item_id from approval"))]


def test_a_later_runs_enqueue_points_the_row_at_the_newest_item(engine: Engine) -> None:
    first_run, _ = make(engine, 1, mode="full")
    go(engine, first_run, FakeChatModel(responses=[saves("v1")]))
    second_run, (second_item,) = make(engine, 1, mode="full")
    go(engine, second_run, FakeChatModel(responses=[saves("v2")]))
    assert queued_items(engine) == [second_item]


def test_the_sweep_leaves_other_runs_alone(engine: Engine) -> None:
    _, other_item = crash_window(engine)
    run_id, _ = make(engine, 0, mode="full")
    go(engine, run_id, FakeChatModel(responses=[saves("unused")]))
    assert item_row(engine, other_item)[0] == "draft_saved"
    assert queue_entries(engine) == 0


def test_a_lease_lost_before_the_enqueue_queues_nothing(engine: Engine) -> None:
    run_id, item_id = crash_window(engine)
    with pytest.raises(LeaseLost):
        go(engine, run_id, FakeChatModel(responses=[saves("unused")]), fence=fails_from(2))
    assert queue_entries(engine) == 0
    assert item_row(engine, item_id)[0] == "draft_saved"


def test_a_lease_lost_before_the_state_commit_moves_no_state(engine: Engine) -> None:
    run_id, item_id = crash_window(engine)
    with pytest.raises(LeaseLost):
        go(engine, run_id, FakeChatModel(responses=[saves("unused")]), fence=fails_from(3))
    assert item_row(engine, item_id)[0] == "draft_saved"


def test_a_failed_enqueue_leaves_the_item_draft_saved(engine: Engine) -> None:
    run_id, _ = crash_window(engine)
    registry = with_enqueue(default_registry(sessions=sessionmaker(engine)), broken)
    go(engine, run_id, FakeChatModel(responses=[saves("unused")]), registry=registry)
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])
    assert queue_entries(engine) == 0


def test_a_failed_memory_enqueue_leaves_the_baseline_item_draft_saved(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="baseline")
    with Session(engine) as session:
        memory = RunMemory.load(session, run_id)
        session.commit()
        registry = with_enqueue(default_registry(approvals=memory), broken)
        process_run(
            run_id, session=session, client=client_for(FakeChatModel(responses=[saves("v1")])),
            registry=registry, limits=Limits(max_steps_item=3),
            switches=SWITCHES[HarnessMode.BASELINE], memory=memory,
        )  # fmt: skip
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])


def test_the_baseline_queues_the_last_save_of_the_turn(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="baseline")
    turn = [call("save_draft", "s1", draft=valid_draft("v1")),
            call("save_draft", "s2", draft=valid_draft("v2"))]  # fmt: skip
    result = go(engine, run_id, FakeChatModel(responses=[ai(tool_calls=turn)]))
    assert result.memory is not None
    assert [a.get("queued", False) for a in result.memory.approvals] == [False, True]


def test_memory_zero_is_no_entry() -> None:
    memory = RunMemory(run_id=1)
    registry = default_registry(approvals=memory)
    env = ToolEnv(1, 2, "sha256:doc", "MK-1")
    save = ToolCall(id="s", name="save_draft", args={"draft": valid_draft()})
    assert registry.execute(save, "item", env).ok
    zero = ToolCall(id="e", name="enqueue_approval", args={"draft_id": "memory-0"})
    result = registry.execute(zero, "run", env)
    assert result.error is not None and result.error.code == "invalid_args"
    assert "queued" not in memory.approvals[0]
