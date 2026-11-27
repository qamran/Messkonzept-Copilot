"""MKC-18.3: transient model errors are retried; when retries run out, or on a setup or auth
error, the run stops (`model_unavailable`, `setup_error`) instead of failing item after item."""

from typing import Any

import pytest
from langchain_core.messages import BaseMessage
from pydantic import Field
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mkc.db.models import Run
from mkc.harness.limits import Limits, StopEvent, StopReason
from mkc.harness.loop import INTERRUPTED, ItemOutcome, process_run
from mkc.harness.states import ItemState
from mkc.models.types import ModelAuthError, ModelConfigError, ReplayMiss, TransientModelError
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import SAVE, Tools, client_for, turns
from tests.harness.test_retry import Clock
from tests.models.fakes import FakeChatModel, ai, fake


class Flaky(FakeChatModel):
    """Raises `errors` in order, one per call, then replies as scripted."""

    errors: list[Exception] = Field(default_factory=list)

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        if self.errors:
            self.seen.append(list(messages))
            raise self.errors.pop(0)
        return super()._generate(messages, *args, **kwargs)


def go(engine: Engine, run_id: int, model: FakeChatModel, clock: Clock, limits: Limits,
       events: list[StopEvent]) -> list[ItemOutcome]:  # fmt: skip
    with Session(engine) as session:
        return process_run(run_id, session=session, client=client_for(model),
                           registry=Tools().registry(), limits=limits, sleep=clock,
                           tracers=[events.append])  # fmt: skip


def stop_reason(engine: Engine, run_id: int) -> str | None:
    with Session(engine) as session:
        return session.get_one(Run, run_id).stop_reason


def test_a_transient_error_is_retried_and_the_item_goes_on(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued")
    model = Flaky(responses=[ai(tool_calls=[SAVE])], errors=[TransientModelError("HTTP 429")])
    clock = Clock()
    outcomes = go(engine, run_id, model, clock, Limits(), [])
    assert [o.state for o in outcomes] == [ItemState.DRAFT_SAVED]
    assert clock.waits == [2] and len(model.seen) == 2


def test_exhausted_retries_stop_the_run_with_model_unavailable(engine: Engine) -> None:
    run_id, ids = make_run(engine, "queued", "queued")
    model = fake(error=TransientModelError("HTTP 503"))
    clock, events = Clock(), []
    outcomes = go(engine, run_id, model, clock, Limits(max_retries_model=2), events)
    assert clock.waits == [2, 4] and len(model.seen) == 3
    assert outcomes == [ItemOutcome(ids[0], ItemState.RUNNING, "model_unavailable", 0, 0)]
    # not one failed item per outage: the run stops, the items keep their place
    assert states(engine, run_id) == ("stopped", ["running", "queued"])
    assert stop_reason(engine, run_id) == "model_unavailable"
    assert events == [
        StopEvent("run", run_id, ids[0], StopReason.MODEL_UNAVAILABLE, "HTTP 503", 0, 0)
    ]


@pytest.mark.parametrize(
    "error",
    [ModelConfigError("no OPENROUTER_API_KEY"), ReplayMiss("k"), ModelAuthError("HTTP 401")],
    ids=["config", "replay-miss", "auth"],
)
def test_setup_errors_stop_the_run(engine: Engine, error: Exception) -> None:
    run_id, ids = make_run(engine, "queued", "queued")
    clock, events = Clock(), []
    outcomes = go(engine, run_id, fake(error=error), clock, Limits(), events)
    assert clock.waits == []  # never retried
    assert outcomes == [ItemOutcome(ids[0], ItemState.RUNNING, "setup_error", 0, 0)]
    # not `done`: the second item was never tried, the first keeps its place
    assert states(engine, run_id) == ("stopped", ["running", "queued"])
    assert stop_reason(engine, run_id) == "setup_error"
    (event,) = events
    assert (event.scope, event.reason, event.detail) == (
        "run", StopReason.SETUP_ERROR, type(error).__name__)  # fmt: skip


def test_a_shutdown_during_a_backoff_leaves_the_item_running(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    model = fake(error=TransientModelError("HTTP 429"))
    outcomes = go(engine, run_id, model, Clock(interrupt_at=1), Limits(), [])
    assert outcomes == [ItemOutcome(item_id, ItemState.RUNNING, INTERRUPTED, 0, 0)]
    assert states(engine, run_id) == ("running", ["running"])  # resumed by the next worker
    assert turns(engine, item_id) == []
