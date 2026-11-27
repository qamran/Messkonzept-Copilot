"""MKC-18.1: run limits stop the run, with the reason in the run row and a `StopEvent`."""

import logging
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from mkc.db.models import Run
from mkc.harness.limits import Limits, StopEvent, StopReason
from mkc.harness.loop import ItemOutcome, process_run
from mkc.harness.states import ItemState
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import READ, SAVE, STEP_COST, Tools, client_for
from tests.models.fakes import FakeChatModel, ai, fake


def go(engine: Engine, run_id: int, model: FakeChatModel, limits: Limits, **kw: Any) -> Any:
    with Session(engine) as session:
        return process_run(run_id, session=session, client=client_for(model),
                           registry=Tools().registry(), limits=limits, **kw)  # fmt: skip


def stop_reason(engine: Engine, run_id: int) -> str | None:
    with Session(engine) as session:
        return session.get_one(Run, run_id).stop_reason


def test_run_step_limit_stops_run(engine: Engine) -> None:
    run_id, ids = make_run(engine, "queued", "queued")
    model = fake(ai(tool_calls=[READ]))  # never saves
    events: list[StopEvent] = []
    outcomes = go(engine, run_id, model, Limits(max_steps_item=5, max_steps_run=3),
                  tracers=[events.append])  # fmt: skip
    assert len(model.seen) == 3  # no model call after the limit
    assert outcomes == [ItemOutcome(ids[0], ItemState.RUNNING, "run_step_limit", 3, 3 * STEP_COST)]
    # the item in flight keeps its checkpoint, the queued one stays queued (decision 58)
    assert states(engine, run_id) == ("stopped", ["running", "queued"])
    assert stop_reason(engine, run_id) == "run_step_limit"
    assert events == [
        StopEvent("run", run_id, ids[0], StopReason.RUN_STEP_LIMIT, None, 3, 3 * STEP_COST)
    ]


def test_cost_limit_stops_run(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    model = fake(ai(tool_calls=[READ]))
    events: list[StopEvent] = []
    go(engine, run_id, model, Limits(max_cost_eur=2 * STEP_COST), tracers=[events.append])
    assert len(model.seen) == 2
    assert states(engine, run_id) == ("stopped", ["running"])
    assert stop_reason(engine, run_id) == "cost_limit"
    assert events == [
        StopEvent("run", run_id, item_id, StopReason.COST_LIMIT, None, 2, 2 * STEP_COST)
    ]


def test_wall_time_stops_run(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued")
    with engine.begin() as conn:  # the run started two hours ago, by the database clock
        conn.execute(text("update run set started_at = now() - interval '2 hours'"))
    model = fake(ai(tool_calls=[SAVE]))
    events: list[StopEvent] = []
    outcomes = go(engine, run_id, model, Limits(max_wall_s=3600), tracers=[events.append])
    assert outcomes == [] and model.seen == []  # stopped before claiming an item
    assert states(engine, run_id) == ("stopped", ["queued"])
    assert stop_reason(engine, run_id) == "wall_time"
    (event,) = events
    assert (event.scope, event.item_id, event.reason) == ("run", None, StopReason.WALL_TIME)
    assert event.steps == 0 and event.cost_eur == 0


def test_started_at_is_set_once_by_the_database_clock(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued", "queued")
    go(engine, run_id, fake(ai(tool_calls=[SAVE])), Limits(), should_stop=_after(1))
    with Session(engine) as session:
        first = session.get_one(Run, run_id).started_at
        assert first is not None
    go(engine, run_id, fake(ai(tool_calls=[SAVE])), Limits())
    with Session(engine) as session:
        assert session.get_one(Run, run_id).started_at == first


def test_usage_is_counted_from_the_database_across_calls(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued")
    first = fake(ai(tool_calls=[READ]))
    go(engine, run_id, first, Limits(), should_stop=_after(2))  # SIGTERM after two turns
    assert len(first.seen) == 2
    second = fake(ai(tool_calls=[READ]))
    go(engine, run_id, second, Limits(max_steps_run=3))
    assert len(second.seen) == 1  # the first call's two turns count
    assert stop_reason(engine, run_id) == "run_step_limit"


def test_a_failing_tracer_does_not_change_the_stop(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(event: StopEvent) -> None:
        raise RuntimeError("tracer down")

    run_id, _ = make_run(engine, "queued")
    with caplog.at_level(logging.INFO, logger="mkc.harness"):
        go(engine, run_id, fake(ai(tool_calls=[READ])), Limits(max_steps_run=1),
           tracers=[broken])  # fmt: skip
    assert states(engine, run_id) == ("stopped", ["running"])
    assert f"run {run_id} stopped: run_step_limit" in caplog.text  # the log line is the trace
    assert "tracer down" in caplog.text


def test_last_item_on_the_limit_turn_settles_the_run(engine: Engine) -> None:
    """MKC-19.1 (finding 18#1): the limits are checked only while an item is left, so a run
    whose last item ends on the turn that reaches a limit settles instead of stopping."""
    run_id, _ = make_run(engine, "queued")
    events: list[StopEvent] = []
    go(engine, run_id, fake(ai(tool_calls=[SAVE])), Limits(max_steps_run=1),
       tracers=[events.append])  # fmt: skip
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])
    assert stop_reason(engine, run_id) is None
    assert events == []


def test_cost_limit_counts_stored_turns_only(engine: Engine) -> None:
    """A model call that raises writes no turn row, so it costs nothing here (known limit)."""
    run_id, _ = make_run(engine, "queued")
    model = fake(error=RuntimeError("boom"))
    go(engine, run_id, model, Limits(max_cost_eur=Decimal("0.000001")))
    assert states(engine, run_id) == ("done", ["failed"])


def _after(n: int) -> Any:
    """`should_stop` that turns true after `n` checks (one check per stored turn)."""
    calls = {"n": 0}

    def should_stop() -> bool:
        calls["n"] += 1
        return calls["n"] > n

    return should_stop
