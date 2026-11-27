"""MKC-18.2: item limits fail the item with its own reason, in the item row and a `StopEvent`."""

from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from mkc.db.models import Item
from mkc.harness.limits import Limits, StopEvent, StopReason
from mkc.harness.loop import ItemOutcome, process_run, run_item
from mkc.harness.prompts import REPROMPT
from mkc.harness.states import ItemState
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import READ, SAVE, STEP_COST, Tools, call, client_for, start, turns
from tests.harness.test_run_limits import _after
from tests.models.fakes import FakeChatModel, ai, fake


def item_run(engine: Engine, item_id: int, model: FakeChatModel, limits: Limits,
             events: list[StopEvent], **kw: Any) -> ItemOutcome:  # fmt: skip
    with Session(engine) as session:
        return run_item(item_id, session=session, client=client_for(model),
                        registry=Tools().registry(), limits=limits,
                        tracers=[events.append], **kw)  # fmt: skip


def item_row(engine: Engine, item_id: int) -> Item:
    with Session(engine) as session:
        item = session.get_one(Item, item_id)
        session.expunge(item)
        return item


def event(run_id: int, item_id: int, reason: StopReason, detail: str | None, steps: int
          ) -> StopEvent:  # fmt: skip
    return StopEvent("item", run_id, item_id, reason, detail, steps, steps * STEP_COST)


# --- step limit --------------------------------------------------------------------------


def test_step_limit_fails_item(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    events: list[StopEvent] = []
    outcome = item_run(engine, item_id, fake(ai(tool_calls=[READ])), Limits(max_steps_item=3),
                       events)  # fmt: skip
    assert outcome == ItemOutcome(item_id, ItemState.FAILED, "step_limit", 3, 3 * STEP_COST)
    assert item_row(engine, item_id).failure_reason == "step_limit"
    assert events == [event(run_id, item_id, StopReason.STEP_LIMIT, None, 3)]


def test_model_error_is_traced_with_its_class(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    events: list[StopEvent] = []
    item_run(engine, item_id, fake(error=RuntimeError("bad")), Limits(), events)
    assert item_row(engine, item_id).failure_reason == "model_error: RuntimeError"
    assert events == [event(run_id, item_id, StopReason.MODEL_ERROR, "RuntimeError", 0)]


# --- tool retries ------------------------------------------------------------------------

BAD_PAGE = call("extract_text", "c1", page=0)  # invalid_args
UNKNOWN = call("nope", "c1")  # unknown_tool: a refusal counts too


@pytest.mark.parametrize(("bad", "tool"), [(BAD_PAGE, "extract_text"), (UNKNOWN, "nope")])
def test_tool_retries_fail_item(engine: Engine, bad: dict[str, Any], tool: str) -> None:
    run_id, (item_id,) = start(engine)
    events: list[StopEvent] = []
    outcome = item_run(engine, item_id, fake(ai(tool_calls=[bad])), Limits(max_retries_tool=2),
                       events)  # fmt: skip
    # failures 1 and 2 are retries the model may make; the third is one too many
    assert (outcome.state, outcome.reason, outcome.steps) == (
        ItemState.FAILED, f"tool_retries: {tool}", 3)  # fmt: skip
    assert len(turns(engine, item_id)) == 3
    assert events == [event(run_id, item_id, StopReason.TOOL_RETRIES, tool, 3)]


def test_tool_retries_are_counted_across_a_resume(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    limits = Limits(max_retries_tool=2)
    first = item_run(engine, item_id, fake(ai(tool_calls=[BAD_PAGE])), limits, [],
                     should_stop=_after(1))  # fmt: skip
    assert (first.state, len(turns(engine, item_id))) == (ItemState.RUNNING, 2)
    model = fake(ai(tool_calls=[BAD_PAGE]))
    second = item_run(engine, item_id, model, limits, [])
    assert len(model.seen) == 1 and second.reason == "tool_retries: extract_text"


def test_a_successful_save_wins_over_a_failure_in_the_same_turn(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    model = fake(ai(tool_calls=[BAD_PAGE, SAVE]))
    outcome = item_run(engine, item_id, model, Limits(max_retries_tool=0), [])
    assert outcome.state is ItemState.DRAFT_SAVED


# --- malformed output: one corrective re-prompt ------------------------------------------


def test_malformed_output_gets_one_reprompt_then_item_fails(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    events: list[StopEvent] = []
    model = fake(ai("I think it is MK 3."), ai("Still no tool."))
    outcome = item_run(engine, item_id, model, Limits(), events)
    assert outcome == ItemOutcome(item_id, ItemState.FAILED, "malformed_output", 2, 2 * STEP_COST)
    assert len(model.seen) == 2
    last = model.seen[1][-1]
    assert isinstance(last, HumanMessage) and last.content == REPROMPT
    assert [r.tool_results for r in turns(engine, item_id)] == [[], []]
    assert events == [event(run_id, item_id, StopReason.MALFORMED_OUTPUT, None, 2)]


def test_a_tool_call_after_the_reprompt_continues_the_item(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    model = fake(ai("Let me think."), ai(tool_calls=[SAVE]))
    assert item_run(engine, item_id, model, Limits(), []).state is ItemState.DRAFT_SAVED


def test_the_reprompt_survives_a_resume(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    first = item_run(engine, item_id, fake(ai("Hmm.")), Limits(), [], should_stop=_after(0))
    assert first.state is ItemState.RUNNING
    model = fake(ai("Still nothing."))
    outcome = item_run(engine, item_id, model, Limits(), [])
    last = model.seen[0][-1]
    assert isinstance(last, HumanMessage) and last.content == REPROMPT
    assert outcome.reason == "malformed_output"  # the re-prompt was used before the resume


def test_no_reprompt_when_max_reprompts_is_zero(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    model = fake(ai("No tools."))
    outcome = item_run(engine, item_id, model, Limits(max_reprompts=0), [])
    assert (outcome.reason, len(model.seen)) == ("malformed_output", 1)


# --- resume cap --------------------------------------------------------------------------


def set_attempts(engine: Engine, item_id: int, n: int) -> None:
    with engine.begin() as conn:
        conn.execute(update(Item).where(Item.id == item_id).values(attempts_without_progress=n))


def resume(engine: Engine, run_id: int, model: FakeChatModel, events: list[StopEvent]) -> Any:
    with Session(engine) as session:
        return process_run(run_id, session=session, client=client_for(model),
                           registry=Tools().registry(), limits=Limits(max_resumes_item=3),
                           tracers=[events.append])  # fmt: skip


def test_resume_limit_fails_item(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)  # claimed: `running`, no turn yet
    set_attempts(engine, item_id, 3)
    events: list[StopEvent] = []
    model = fake(ai(tool_calls=[SAVE]))
    outcomes = resume(engine, run_id, model, events)
    assert model.seen == []
    assert outcomes == [ItemOutcome(item_id, ItemState.FAILED, "resume_limit", 0, 0 * STEP_COST)]
    assert states(engine, run_id) == ("done", ["failed"])
    assert item_row(engine, item_id).attempts_without_progress == 4
    assert events == [event(run_id, item_id, StopReason.RESUME_LIMIT, None, 0)]


def test_a_resume_counts_an_attempt(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    set_attempts(engine, item_id, 2)
    resume(engine, run_id, fake(error=RuntimeError("crash-like")), [])  # no turn stored
    assert item_row(engine, item_id).attempts_without_progress == 3


def test_a_stored_turn_resets_the_attempts(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    set_attempts(engine, item_id, 2)  # the resume makes it 3: still allowed
    resume(engine, run_id, fake(ai(tool_calls=[READ]), ai(tool_calls=[SAVE])), [])
    row = item_row(engine, item_id)
    assert (row.state, row.attempts_without_progress) == ("draft_saved", 0)


def test_a_first_claim_is_not_a_resume(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    resume(engine, run_id, fake(error=RuntimeError("x")), [])
    assert item_row(engine, item_id).attempts_without_progress == 0
