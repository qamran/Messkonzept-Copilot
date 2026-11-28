"""MKC-23: two edges of the approval path.

- MKC-17 finding 2: tool writes are not fenced, so a worker that lost its lease could still
  replace a draft in its turn in flight. Pinned: with the lease held by another worker,
  `run_item` (with the real `fence`) ends in `LeaseLost` and has written no draft. How
  `save_draft` learns of the lost lease is the development agent's choice.
- PR #167 finding 7 (decision 60): a baseline item can be `draft_saved` with no `draft` row;
  approval code must not assume one. Pinned: a baseline run's save ends `pending_approval`
  (the enqueue works in memory) with no `draft` and no `approval` row, and a baseline run
  with a row-less `draft_saved` item runs without an error.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, func, inspect, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Draft, Run
from mkc.harness.limits import Limits
from mkc.harness.loop import run_item
from mkc.harness.registry import default_registry
from mkc.worker.lease import LeaseLost, fence
from tests.extraction.drafts import valid_draft
from tests.harness.conftest import states
from tests.harness.test_baseline import go, make
from tests.harness.test_loop import call, client_for, start
from tests.models.fakes import FakeChatModel, ai

SAVE = ai(tool_calls=[call("save_draft", "s1", draft=valid_draft())])


@pytest.fixture(autouse=True)
def empty_queue(engine: Engine) -> Iterator[None]:
    with engine.begin() as conn:
        if inspect(conn).has_table("approval"):
            conn.execute(text("truncate approval restart identity cascade"))
    yield


def drafts(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Draft)) or 0


def queue_entries(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("select count(*) from approval")).scalar_one())


def test_a_worker_that_lost_its_lease_writes_no_draft(engine: Engine) -> None:
    run_id, (item_id,) = start(engine)
    with Session(engine) as session, session.begin():
        session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(lease_owner="worker-b", lease_expires_at=datetime.now(UTC) + timedelta(hours=1))
        )
    with Session(engine) as session, pytest.raises(LeaseLost):
        run_item(
            item_id,
            session=session,
            client=client_for(FakeChatModel(responses=[SAVE])),
            registry=default_registry(sessions=sessionmaker(engine)),
            limits=Limits(max_steps_item=3),
            fence=lambda s: fence(s, run_id, owner="worker-a"),
        )
    assert drafts(engine) == 0, "worker-a's save must not reach the draft table"


def test_a_baseline_save_is_queued_in_memory_only(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="baseline")
    result = go(engine, run_id, FakeChatModel(responses=[SAVE]))
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval"])
    assert result.memory is not None and len(result.memory.approvals) >= 1
    assert drafts(engine) == 0
    assert queue_entries(engine) == 0


def test_a_rowless_draft_saved_item_breaks_no_full_run(engine: Engine) -> None:
    """The path the crash-window enqueue walks (`draft_saved` without a queue row), for an
    item whose draft was in memory: no error, nothing queued. Its state is not pinned."""
    run_id, (item_id,) = make(engine, 1, mode="full")
    with Session(engine) as session, session.begin():
        session.execute(text("update item set state = 'draft_saved' where id = :id"),
                        {"id": item_id})  # fmt: skip
    model = FakeChatModel(responses=[SAVE])
    go(engine, run_id, model)
    assert model.seen == []
    assert drafts(engine) == 0
    assert queue_entries(engine) == 0


def test_a_rowless_draft_saved_baseline_item_breaks_nothing(engine: Engine) -> None:
    run_id, (done, _todo) = make(engine, 2, mode="baseline")
    with Session(engine) as session, session.begin():
        session.execute(text("update item set state = 'draft_saved' where id = :id"),
                        {"id": done})  # fmt: skip
    go(engine, run_id, FakeChatModel(responses=[SAVE]))
    run_state, item_states = states(engine, run_id)
    assert run_state == "awaiting_approval"
    assert item_states[1] == "pending_approval"
    assert drafts(engine) == 0
