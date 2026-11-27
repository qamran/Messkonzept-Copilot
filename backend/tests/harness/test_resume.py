"""MKC-16.3: an interrupted item resumes at its last complete turn (design 8.3).

A crash is `Crash(BaseException)`: the loop and the registry catch `Exception` only, so it
leaves the process like a kill would. Every resume runs in a fresh session.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mkc.db.models import Turn
from mkc.harness.checkpoint import load_resume_context
from mkc.harness.loop import ItemOutcome, process_run, run_item
from mkc.harness.states import ItemState
from mkc.harness.tools import ToolEnv
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import (
    SAVE,
    STEP_COST,
    PageArgs,
    Tools,
    call,
    client_for,
    start,
    turns,
)
from tests.models.fakes import FakeChatModel, ai, fake


class Crash(BaseException):
    """The process dies here."""


class CrashingModel(FakeChatModel):
    """Crashes on model call number `crash_at` (1-based); `on_call` runs before each call."""

    crash_at: int | None = None
    on_call: Callable[[], None] | None = None

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        if self.on_call is not None:
            self.on_call()
        if self.crash_at == len(self.seen) + 1:
            self.seen.append(list(messages))
            raise Crash
        return super()._generate(messages, *args, **kwargs)


def read(page: int) -> dict[str, Any]:
    return call("extract_text", f"r{page}", page=page)


def crashing(*replies: AIMessage, at: int) -> CrashingModel:
    return CrashingModel(responses=list(replies), crash_at=at)


def go(engine: Engine, item_id: int, model: FakeChatModel, tools: Tools, **kw: Any) -> ItemOutcome:
    with Session(engine) as session:
        steps = kw.pop("max_steps", 6)
        return run_item(item_id, session=session, client=client_for(model),
                        registry=tools.registry(), max_steps=steps, **kw)  # fmt: skip


def crash_after(engine: Engine, k: int, tools: Tools | None = None, **kw: Any) -> int:
    """A claimed item that crashed on model call k+1, after k complete turns."""
    _, (item_id,) = start(engine)
    model = crashing(*[ai(tool_calls=[read(n)]) for n in range(1, k + 1)], at=k + 1)
    with pytest.raises(Crash):
        go(engine, item_id, model, tools or Tools(), **kw)
    assert [t.number for t in turns(engine, item_id)] == list(range(1, k + 1))
    return item_id


def test_crash_after_turn_k_resumes_at_k_plus_1(engine: Engine) -> None:
    item_id = crash_after(engine, 2)
    model = fake(ai(tool_calls=[SAVE]))
    outcome = go(engine, item_id, model, Tools())
    assert outcome == ItemOutcome(item_id, ItemState.DRAFT_SAVED, None, 3, 3 * STEP_COST)
    assert [t.number for t in turns(engine, item_id)] == [1, 2, 3]
    assert len(model.seen) == 1  # completed turns are not re-requested


def test_the_step_cap_counts_across_a_crash(engine: Engine) -> None:
    item_id = crash_after(engine, 2)
    model = fake(ai(tool_calls=[read(3)]))
    outcome = go(engine, item_id, model, Tools(), max_steps=3)
    assert (outcome.reason, outcome.steps) == ("step_limit", 3)
    assert len(model.seen) == 1


class CrashingTools(Tools):
    """`extract_text` dies on its `crash_on`-th call."""

    def __init__(self, crash_on: int) -> None:
        super().__init__()
        self.calls, self.crash_on = 0, crash_on

    def extract_text(self, args: PageArgs, env: ToolEnv) -> Any:
        self.calls += 1
        if self.calls == self.crash_on:
            raise Crash
        return super().extract_text(args, env)


def test_inflight_turn_is_discarded(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    first = fake(*[ai(tool_calls=[read(n)]) for n in (1, 2, 3)])
    with pytest.raises(Crash):  # dies inside turn 3's tool call
        go(engine, item_id, first, CrashingTools(crash_on=3))
    assert [t.number for t in turns(engine, item_id)] == [1, 2]

    second = fake(ai(tool_calls=[SAVE]))
    assert go(engine, item_id, second, Tools()).state is ItemState.DRAFT_SAVED
    rows = turns(engine, item_id)
    assert [t.number for t in rows] == [1, 2, 3]  # turn 3 exists exactly once: the re-request
    assert rows[2].assistant["tool_calls"][0]["name"] == "save_draft"
    # the re-request is answered from turn 2, the last complete turn
    assert [m.tool_call_id for m in second.seen[0] if isinstance(m, ToolMessage)] == ["r2"]


def test_resume_context_is_task_summary_and_last_turn(engine: Engine) -> None:
    item_id = crash_after(engine, 3)
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools())
    system, task, assistant, result = model.seen[0]
    assert isinstance(system, SystemMessage)
    assert isinstance(task, HumanMessage)
    content = str(task.content)
    assert "<item_task>" in content and "MK-1" in content
    summary = content[content.index("<earlier_turns>") : content.index("</earlier_turns>")]
    assert '"tool": "extract_text"' in summary and '"page": 1' in summary
    assert '"page": 2' in summary and '"page": 3' not in summary  # turn 3 is given in full
    assert "<" not in summary.removeprefix("<earlier_turns>")
    assert isinstance(assistant, AIMessage) and [c["id"] for c in assistant.tool_calls] == ["r3"]
    assert isinstance(result, ToolMessage) and result.tool_call_id == "r3"
    assert str(result.content).startswith('<tool_result name="extract_text">')


def test_zero_stored_turns_is_a_fresh_start(engine: Engine) -> None:
    item_id = crash_after(engine, 0)
    model = fake(ai(tool_calls=[SAVE]))
    assert go(engine, item_id, model, Tools()).steps == 1
    assert [type(m) for m in model.seen[0]] == [SystemMessage, HumanMessage]
    assert "<earlier_turns>" not in str(model.seen[0][1].content)


def test_one_stored_turn_has_no_summary(engine: Engine) -> None:
    item_id = crash_after(engine, 1)
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools())
    assert [type(m) for m in model.seen[0]] == [SystemMessage, HumanMessage, AIMessage, ToolMessage]
    assert "<earlier_turns>" not in str(model.seen[0][1].content)


def test_a_blob_ref_in_the_last_turn_is_rehydrated(engine: Engine) -> None:
    item_id = crash_after(engine, 1, Tools(text="Seite " * 400), inline_max_bytes=1000)
    assert "result_ref" in turns(engine, item_id)[0].tool_results[0]
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools())
    assert "Seite Seite" in str(model.seen[0][-1].content)


def test_load_resume_context_counts_steps_and_cost(engine: Engine) -> None:
    item_id = crash_after(engine, 2)
    with Session(engine) as session:
        context = load_resume_context(session, item_id)
    assert (context.next_number, context.steps_done) == (3, 2)
    assert context.cost_eur == 2 * STEP_COST
    assert [m.role for m in context.messages] == ["system", "user", "assistant", "tool"]


def test_process_run_resumes_a_running_item_before_claiming_queued_ones(engine: Engine) -> None:
    run_id, ids = make_run(engine, "queued", "running")
    tools = Tools()
    with Session(engine) as session:
        outcomes = process_run(run_id, session=session, client=client_for(
            fake(ai(tool_calls=[SAVE]), ai(tool_calls=[SAVE]))), registry=tools.registry(),
            max_steps=5)  # fmt: skip
    assert [o.item_id for o in outcomes] == [ids[1], ids[0]]
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved", "draft_saved"])


def test_a_second_writer_on_the_same_turn_raises_and_does_not_fail_the_item(
    engine: Engine,
) -> None:
    _, (item_id,) = start(engine)

    def other_worker_writes_turn_1() -> None:
        with Session(engine) as other, other.begin():
            other.add(Turn(item_id=item_id, number=1, assistant={}, tool_results=[],
                           cost_eur=Decimal(0)))  # fmt: skip

    model = CrashingModel(responses=[ai(tool_calls=[read(1)])], on_call=other_worker_writes_turn_1)
    with pytest.raises(IntegrityError):
        go(engine, item_id, model, Tools())
    with Session(engine) as session:
        from mkc.db.models import Item

        assert session.get_one(Item, item_id).state == "running"
