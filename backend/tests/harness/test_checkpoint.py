"""MKC-16.1: a turn is stored in one transaction, and only as a complete turn."""

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from mkc.db.models import Item, Turn
from mkc.harness.checkpoint import TurnRecord, save_turn
from mkc.harness.loop import run_item
from mkc.harness.tools import ToolRegistry
from mkc.models.types import Message, ToolCall
from tests.harness.test_loop import READ, SAVE, Tools, call, client_for, start, turns
from tests.models.fakes import ai, fake


def assistant(*ids: str) -> Message:
    calls = [ToolCall(id=i, name="extract_text", args={"page": 1}) for i in ids]
    return Message(role="assistant", content="", tool_calls=calls)


def result(call_id: str) -> dict[str, Any]:
    return {"tool_call_id": call_id, "name": "extract_text", "result": {"ok": True}}


def record(item_id: int, message: Message, results: list[dict[str, Any]]) -> TurnRecord:
    return TurnRecord(item_id=item_id, number=1, assistant=message, results=results,
                      cost_eur=Decimal("0.0003"))  # fmt: skip


@pytest.mark.parametrize(
    "result_ids",
    [
        [],  # a call without its result
        ["c1"],  # the second call is unanswered
        ["c1", "c2", "c3"],  # a result without its call
        ["c1", "c1"],  # one call answered twice
        ["c2", "c1"],  # results out of call order
    ],
)
def test_checkpoint_never_splits_tool_call_and_result(
    engine: Engine, result_ids: list[str]
) -> None:
    _, (item_id,) = start(engine)
    with Session(engine) as session:
        turn = record(item_id, assistant("c1", "c2"), [result(i) for i in result_ids])
        with pytest.raises(ValueError, match="pair"):
            save_turn(session, turn)
        session.commit()
    assert turns(engine, item_id) == []


def test_save_turn_stores_a_complete_turn_without_committing(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    with Session(engine) as session:
        save_turn(session, record(item_id, assistant("c1"), [result("c1")]))
        assert turns(engine, item_id) == []  # the caller commits
        session.commit()
    (row,) = turns(engine, item_id)
    assert row.number == 1 and row.cost_eur == Decimal("0.0003")
    assert row.tool_results == [result("c1")]


class Exploding(Tools):
    """`execute` raises on the second call of a turn (a harness bug, not a tool error)."""

    def registry(self) -> ToolRegistry:
        registry = super().registry()
        calls = 0

        class Broken:
            def for_context(self, ctx: Any) -> Any:
                return registry.for_context(ctx)

            def execute(self, *args: Any) -> Any:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise KeyError("bad ctx")
                return registry.execute(*args)

        return Broken()  # type: ignore[return-value]


def test_a_tool_error_turn_answers_every_call(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    reply = ai(tool_calls=[READ, call("extract_text", "c5", page=2), call("save_draft", "c6")])
    with Session(engine) as session:
        outcome = run_item(item_id, session=session, client=client_for(fake(reply)),
                           registry=Exploding().registry(), max_steps=3)  # fmt: skip
    assert outcome.reason == "tool_error: KeyError"
    (row,) = turns(engine, item_id)
    assert [r["tool_call_id"] for r in row.tool_results] == ["c1", "c5", "c6"]
    first, escaped, unanswered = (r["result"] for r in row.tool_results)
    assert first["ok"] is True
    assert escaped["error"]["code"] == "tool_failed"
    assert "KeyError" in escaped["error"]["message"]
    assert unanswered["error"] == {
        "code": "tool_failed",
        "message": "not run: an earlier call in this turn failed",
    }


def test_duplicate_call_ids_are_made_unique(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    twice = [call("extract_text", "dup", page=1), call("extract_text", "dup", page=2)]
    model = fake(ai(tool_calls=twice), ai(tool_calls=[SAVE]))
    with Session(engine) as session:
        run_item(item_id, session=session, client=client_for(model),
                 registry=Tools().registry(), max_steps=3)  # fmt: skip
    first = turns(engine, item_id)[0]
    assert [c["id"] for c in first.assistant["tool_calls"]] == ["dup-0", "dup-1"]
    assert [r["tool_call_id"] for r in first.tool_results] == ["dup-0", "dup-1"]


def test_the_last_turn_and_the_end_state_are_one_commit(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    model = fake(ai(tool_calls=[READ]), ai(tool_calls=[SAVE]))
    commits: list[tuple[bool, bool]] = []  # per commit: (carries turn 2, carries the end state)
    with Session(engine) as session:

        @event.listens_for(session, "before_commit")
        def fail_the_final_commit(s: Session) -> None:
            turn_2 = any(isinstance(o, Turn) and o.number == 2 for o in s.new)
            end_state = any(isinstance(o, Item) and o.state != "running" for o in s.dirty)
            commits.append((turn_2, end_state))
            if turn_2 or end_state:
                raise RuntimeError("database gone")

        with pytest.raises(RuntimeError, match="database gone"):
            run_item(item_id, session=session, client=client_for(model),
                     registry=Tools().registry(), max_steps=3)  # fmt: skip
    # the one commit that carries either carries both: a split would show (True, False) first
    assert [c for c in commits if any(c)] == [(True, True)]
    assert [r.number for r in turns(engine, item_id)] == [1]
    with Session(engine) as session:
        assert session.get_one(Item, item_id).state == "running"
