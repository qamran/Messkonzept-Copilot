"""MKC-23: `save_draft` takes a `MesskonzeptDraft`, and the harness enqueues the approval
exactly once (design 8.1 and 8.2, decisions 53 and 56, E4 "repeated side effects: 0").

Pinned (assumptions for the coordinator):

- The approval queue is a table named `approval`, one row per queued draft; these tests
  count its rows (each test has one record key). The harness (not `save_draft`) runs
  `enqueue_approval` on a successful save: the item goes `draft_saved -> pending_approval`.
- A run with a `draft_saved` item and no queue entry (a crash in between) gets it queued by
  the next `execute_run`, once; `FaultPlan(kill_during_approval=1)` still fires between the
  two states.
- The user's ruling (decision 56 note): a save for a key whose draft is still pending
  approval replaces the body and keeps one queue entry; once the item that owns the draft is
  `approved` or `committed`, the save is refused with the error code `draft_locked`, the
  body stays, and the saving item fails with `draft_locked` in its `failure_reason`, right
  after that turn.
- `save_draft` refuses (no write) when its item is not `running` (MKC-17 finding 2).
"""

from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import Engine, inspect, text, update
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Draft, Item
from mkc.harness.faults import FaultInjector, FaultPlan, InjectedKill
from mkc.harness.registry import default_registry
from mkc.harness.tools import ToolEnv, ToolRegistry
from mkc.models.types import ToolCall
from tests.extraction.drafts import valid_draft
from tests.harness.conftest import make_run, states
from tests.harness.test_baseline import go, make
from tests.harness.test_loop import call
from tests.models.fakes import FakeChatModel, ai


@pytest.fixture(autouse=True)
def empty_queue(engine: Engine) -> Iterator[None]:
    """The `engine` fixture's cascade may not reach the queue table: empty it too."""
    with engine.begin() as conn:
        if inspect(conn).has_table("approval"):
            conn.execute(text("truncate approval restart identity cascade"))
    yield


def queue_entries(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("select count(*) from approval")).scalar_one())


def bodies(engine: Engine) -> list[dict[str, Any]]:
    with Session(engine) as session:
        return [d.body for d in session.query(Draft).order_by(Draft.id)]


def item_row(engine: Engine, item_id: int) -> tuple[str, str | None]:
    with Session(engine) as session:
        item = session.get_one(Item, item_id)
        return item.state, item.failure_reason


def set_state(engine: Engine, item_id: int, state: str) -> None:
    with Session(engine) as session, session.begin():
        session.execute(update(Item).where(Item.id == item_id).values(state=state))


def saves(title: str, n: int = 1) -> Any:
    return ai(tool_calls=[call("save_draft", f"s{n}", draft=valid_draft(title))])


def env_for(run_id: int, item_id: int) -> ToolEnv:
    return ToolEnv(run_id, item_id, "sha256:doc", "MK-1")


def save(engine: Engine, env: ToolEnv, body: dict[str, Any]) -> Any:
    registry = default_registry(sessions=sessionmaker(engine))
    return registry.execute(ToolCall(id="s", name="save_draft", args={"draft": body}), "item", env)


# --- save_draft takes a MesskonzeptDraft -------------------------------------------------


def test_save_draft_refuses_a_free_dict(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    result = save(engine, env_for(run_id, item_id), {"lbs": "9992000000026"})
    assert result.error is not None and result.error.code == "invalid_args"
    assert bodies(engine) == []


def test_save_draft_refuses_a_key_inside_the_draft(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    body = valid_draft() | {"document_hash": "sha256:other", "concept_key": "MK-9"}
    result = save(engine, env_for(run_id, item_id), body)
    assert result.error is not None and result.error.code == "invalid_args"
    assert bodies(engine) == []


def test_save_draft_stores_the_validated_draft(engine: Engine) -> None:
    from mkc.extraction.draft import MesskonzeptDraft

    run_id, (item_id,) = make_run(engine, "running")
    result = save(engine, env_for(run_id, item_id), valid_draft())
    assert result.ok, result.error
    assert set(result.data) == {"draft_id"}
    (body,) = bodies(engine)
    assert MesskonzeptDraft.model_validate(body) == MesskonzeptDraft.model_validate(valid_draft())


def test_save_draft_does_not_enqueue(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    assert save(engine, env_for(run_id, item_id), valid_draft()).ok
    assert item_row(engine, item_id)[0] == "running"
    assert queue_entries(engine) == 0, "the harness enqueues, never save_draft"


@pytest.mark.parametrize("state", ["queued", "draft_saved", "pending_approval", "failed"])
def test_save_draft_refuses_an_item_that_is_not_running(engine: Engine, state: str) -> None:
    run_id, (item_id,) = make_run(engine, state)
    result = save(engine, env_for(run_id, item_id), valid_draft())
    assert not result.ok
    assert bodies(engine) == [], "a worker that lost its item writes no draft"


# --- the harness enqueues exactly once -------------------------------------------------


def test_saved_draft_is_enqueued_for_approval_once(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="full")
    go(engine, run_id, FakeChatModel(responses=[saves("v1")]))
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval"])
    assert queue_entries(engine) == 1
    again = FakeChatModel(responses=[saves("v2")])
    go(engine, run_id, again)  # a re-run of the same run
    assert again.seen == [], "a queued item is not extracted again"
    assert queue_entries(engine) == 1
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval"])


def test_a_draft_saved_item_is_enqueued_by_the_next_run(engine: Engine) -> None:
    """The crash window: the draft and `draft_saved` are durable, the queue entry is not."""
    run_id, (item_id,) = make(engine, 1, mode="full")
    set_state(engine, item_id, "draft_saved")
    with Session(engine) as session, session.begin():
        session.add(Draft(document_hash="sha256:doc", concept_key="MK-1", item_id=item_id,
                          body=valid_draft()))  # fmt: skip
    model = FakeChatModel(responses=[saves("unused")])
    go(engine, run_id, model)
    assert model.seen == []
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval"])
    assert queue_entries(engine) == 1
    go(engine, run_id, model)
    assert queue_entries(engine) == 1


def test_a_kill_during_approval_then_resume_enqueues_once(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="full")
    injector = FaultInjector(FaultPlan(kill_during_approval=1))
    with pytest.raises(InjectedKill):
        go(engine, run_id, FakeChatModel(responses=[saves("v1")]), faults=injector)
    assert states(engine, run_id) == ("running", ["draft_saved"])
    assert queue_entries(engine) == 0
    again = FakeChatModel(responses=[saves("v2")])
    go(engine, run_id, again, faults=injector)
    assert again.seen == [], "the saved draft is not extracted again"
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval"])
    assert queue_entries(engine) == 1


# --- the user's ruling on a later save (decision 56 note) ------------------------------


def test_a_later_save_while_pending_replaces_the_body_and_keeps_one_entry(
    engine: Engine,
) -> None:
    first_run, _ = make(engine, 1, mode="full")
    go(engine, first_run, FakeChatModel(responses=[saves("v1")]))
    second_run, (second_item,) = make(engine, 1, mode="full")  # the same document and concept
    go(engine, second_run, FakeChatModel(responses=[saves("v2")]))
    assert [b["title"] for b in bodies(engine)] == ["v2"]
    assert queue_entries(engine) == 1
    assert item_row(engine, second_item)[0] == "pending_approval"


@pytest.mark.parametrize("decided", ["approved", "committed"])
def test_a_save_after_approval_is_draft_locked(engine: Engine, decided: str) -> None:
    first_run, (first_item,) = make(engine, 1, mode="full")
    go(engine, first_run, FakeChatModel(responses=[saves("v1")]))
    set_state(engine, first_item, decided)
    second_run, (second_item,) = make_run(engine, "running")
    result = save(engine, env_for(second_run, second_item), valid_draft("v2"))
    assert result.error is not None and result.error.code == "draft_locked"
    assert [b["title"] for b in bodies(engine)] == ["v1"], "the approved record is unchanged"
    assert queue_entries(engine) == 1


@pytest.mark.parametrize("decided", ["approved", "committed"])
def test_a_draft_locked_save_fails_the_item(engine: Engine, decided: str) -> None:
    first_run, (first_item,) = make(engine, 1, mode="full")
    go(engine, first_run, FakeChatModel(responses=[saves("v1")]))
    set_state(engine, first_item, decided)
    second_run, (second_item,) = make(engine, 1, mode="full")
    model = FakeChatModel(responses=[saves("v2")])
    go(engine, second_run, model)
    state, reason = item_row(engine, second_item)
    assert state == "failed"
    assert reason is not None and "draft_locked" in reason
    assert len(model.seen) == 1, "the item fails on the refused save, without retries"
    assert [b["title"] for b in bodies(engine)] == ["v1"]
    assert item_row(engine, first_item)[0] == decided


# --- a save in a turn that then breaks -------------------------------------------------


def test_a_save_followed_by_a_broken_call_is_not_enqueued(engine: Engine) -> None:
    """Pre-PR minor (MKC-16): the turn saves, then a later call escapes (its result can't be
    serialised). The item fails and nothing is queued; the draft row may stay (`drafts.py`:
    go by the item state, not the row)."""
    run_id, (item_id,) = make(engine, 1, mode="full")
    base = default_registry(sessions=sessionmaker(engine))

    def broken(args: Any, env: ToolEnv) -> Any:
        return object()  # not JSON: escapes `_run_calls`

    item = [replace(t, fn=broken) if t.name == "extract_text" else t
            for t in base.for_context("item")]  # fmt: skip
    registry = ToolRegistry(item=item, run=base.for_context("run"))
    turn = [call("save_draft", "s1", draft=valid_draft()), call("extract_text", "r1", page=1)]
    go(engine, run_id, FakeChatModel(responses=[ai(tool_calls=turn)]), registry=registry)
    assert item_row(engine, item_id)[0] == "failed"
    assert queue_entries(engine) == 0
