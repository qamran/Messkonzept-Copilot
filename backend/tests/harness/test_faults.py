"""MKC-20.3: failure injection, one test per fault type (feature 25, E4, decision 60).

Every fault goes through the real path: a 429 through `call_model`'s backoff, a malformed
reply through the re-prompt, a tool timeout through the tool-retry count, and a kill
(`InjectedKill`, a `BaseException`) leaves the loop like a dead process.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from mkc.config import Settings
from mkc.db.models import Draft
from mkc.harness.faults import FaultInjector, FaultPlan, InjectedKill, load_fault_plans
from mkc.harness.prompts import REPROMPT
from mkc.models.types import ModelReply, ToolCall, TransientModelError, Usage
from tests.harness.conftest import states
from tests.harness.test_baseline import READ, go, make, saved
from tests.harness.test_loop import Tools, turns
from tests.models.fakes import FakeChatModel

E4_FILE = Path(__file__).resolve().parents[2] / "data" / "e4_faults.yaml"


def faulty(engine: Engine, run_id: int, model: FakeChatModel, plan: FaultPlan, **kw: Any) -> Any:
    waits: list[float] = kw.pop("waits", [])
    injector = kw.pop("injector", None) or FaultInjector(plan)
    return go(engine, run_id, model, faults=injector,
              sleep=lambda s: waits.append(s) or False, **kw)  # fmt: skip


def drafts(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Draft)) or 0


def test_rate_limit_is_retried(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="full")
    model, waits = FakeChatModel(responses=[saved(1)]), []
    faulty(engine, run_id, model, FaultPlan(rate_limit_at=1), waits=waits)
    assert waits == [2.0]  # one backoff (MKC-18 default base)
    assert len(model.seen) == 1  # the injected 429 never reached the model
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])


def test_tool_timeout_counts_as_a_tool_failure(engine: Engine) -> None:
    run_id, (item_id,) = make(engine, 1, mode="full")
    tools = Tools()
    model = FakeChatModel(responses=[READ, saved(1)])
    faulty(engine, run_id, model, FaultPlan(timeout_at=1), registry=tools.registry())
    result = turns(engine, item_id)[0].tool_results[0]["result"]
    assert result["ok"] is False
    assert result["error"]["code"] == "timeout"
    assert '"timeout"' in model.seen[1][-1].content  # the model was told
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])


def test_malformed_reply_gets_the_reprompt(engine: Engine) -> None:
    run_id, (item_id,) = make(engine, 1, mode="full")
    model = FakeChatModel(responses=[saved(1)])
    faulty(engine, run_id, model, FaultPlan(malformed_at=1))
    assert len(model.seen) == 1  # the malformed reply did not come from the model
    assert model.seen[0][-1].content == REPROMPT
    first = turns(engine, item_id)[0]
    assert first.assistant["tool_calls"] == [] and first.cost_eur == 0
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])


def test_kill_at_turn_resumes_in_full(engine: Engine) -> None:
    run_id, (item_id,) = make(engine, 1, mode="full")
    plan = FaultPlan(kill_at_turn=2)
    injector = FaultInjector(plan)
    first = FakeChatModel(responses=[READ, READ, saved(1)])
    with pytest.raises(InjectedKill):
        faulty(engine, run_id, first, plan, injector=injector)
    assert len(first.seen) == 2  # turn 2 reached the model, then the process died
    assert [t.number for t in turns(engine, item_id)] == [1]  # turn 2 was in flight
    assert states(engine, run_id) == ("running", ["running"])
    again = FakeChatModel(responses=[READ, saved(1)])
    faulty(engine, run_id, again, plan, injector=injector)  # the same plan: fired once
    assert [t.number for t in turns(engine, item_id)] == [1, 2, 3]
    assert injector.fired == ["kill_at_turn"]


def test_kill_at_turn_restarts_baseline_from_zero(engine: Engine) -> None:
    run_id, _ = make(engine, 1)
    plan = FaultPlan(kill_at_turn=2)
    with pytest.raises(InjectedKill):
        faulty(engine, run_id, FakeChatModel(responses=[READ, READ]), plan)
    assert states(engine, run_id) == ("running", ["queued"])
    again = FakeChatModel(responses=[READ, saved(1)])
    faulty(engine, run_id, again, FaultPlan())  # a new process, no fault
    assert len(again.seen) == 2  # turn 1 was redone
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])


def test_kill_during_approval_keeps_the_draft_in_full(engine: Engine) -> None:
    run_id, _ = make(engine, 2, mode="full")
    plan = FaultPlan(kill_during_approval=1)
    with pytest.raises(InjectedKill):
        faulty(engine, run_id, FakeChatModel(responses=[saved(1), saved(2)]), plan)
    assert states(engine, run_id) == ("running", ["draft_saved", "queued"])
    assert drafts(engine) == 1
    again = FakeChatModel(responses=[saved(2)])
    faulty(engine, run_id, again, FaultPlan())
    assert len(again.seen) == 1  # item 1 was not redone
    assert drafts(engine) == 2
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved", "draft_saved"])


def test_kill_during_approval_loses_the_draft_in_baseline(engine: Engine) -> None:
    run_id, _ = make(engine, 2)
    plan = FaultPlan(kill_during_approval=1)
    with pytest.raises(InjectedKill):
        faulty(engine, run_id, FakeChatModel(responses=[saved(1), saved(2)]), plan)
    assert states(engine, run_id) == ("running", ["queued", "queued"])
    again = FakeChatModel(responses=[saved(1), saved(2)])
    result = faulty(engine, run_id, again, FaultPlan())
    assert len(again.seen) == 2  # item 1 was extracted again
    assert len(result.memory.approvals) == 2
    assert drafts(engine) == 0


def _reply() -> ModelReply:
    usage = Usage(input_tokens=1, output_tokens=1, cost_eur=0.0)
    return ModelReply(text="", usage=usage, model_id="m", latency_ms=1)


def test_each_fault_fires_once() -> None:
    injector = FaultInjector(FaultPlan(rate_limit_at=1, timeout_at=1))
    model = injector.model(_reply)
    with pytest.raises(TransientModelError):
        model()
    assert model().text == "" and model().text == ""
    timed_out = injector.tool(ToolCall(id="a", name="extract_text"))
    assert timed_out is not None and timed_out.error is not None
    assert injector.tool(ToolCall(id="b", name="extract_text")) is None
    assert injector.fired == ["rate_limit_at", "timeout_at"]


def test_fault_plans_load_from_yaml(tmp_path: Path) -> None:
    plans = load_fault_plans(E4_FILE)
    assert set(plans) == {"no_faults", "tool_timeout", "rate_limit", "malformed",
                          "kill_at_turn", "kill_during_approval"}  # fmt: skip
    assert plans["no_faults"] == FaultPlan()
    for name, plan in plans.items():
        assert len(plan.model_dump(exclude_none=True)) == (0 if name == "no_faults" else 1)
    bad = tmp_path / "bad.yaml"
    bad.write_text("x:\n  kill_at_step: 2\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_fault_plans(bad)
    bad.write_text("x:\n  kill_at_turn: 0\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_fault_plans(bad)


def test_no_fault_plan_comes_from_a_setting() -> None:
    assert not [name for name in Settings.model_fields if "fault" in name]
