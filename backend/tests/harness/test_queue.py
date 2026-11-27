"""MKC-15.4: the work queue (`next_item`) and run settling (`settle_run`)."""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mkc.harness.queue import next_item, settle_run
from mkc.harness.states import RunState
from tests.harness.conftest import make_run, states


def claim(engine: Engine, run_id: int) -> int | None:
    with Session(engine) as session, session.begin():
        item = next_item(session, run_id)
        return None if item is None else item.id


def settle(engine: Engine, run_id: int) -> RunState:
    with Session(engine) as session, session.begin():
        return settle_run(session, run_id)


def test_next_item_claims_the_oldest_queued_item(engine: Engine) -> None:
    run_id, ids = make_run(engine, "draft_saved", "queued", "queued")
    assert claim(engine, run_id) == ids[1]
    assert states(engine, run_id) == ("running", ["draft_saved", "running", "queued"])
    assert claim(engine, run_id) == ids[2]
    assert claim(engine, run_id) is None


@pytest.mark.parametrize("run_state", ["awaiting_approval", "done", "stopped"])
def test_next_item_serves_only_running_runs(engine: Engine, run_state: str) -> None:
    run_id, _ = make_run(engine, "queued", run_state=run_state)
    assert claim(engine, run_id) is None
    assert states(engine, run_id) == (run_state, ["queued"])


def test_next_item_ignores_other_runs(engine: Engine) -> None:
    other, _ = make_run(engine, "queued")
    run_id, _ = make_run(engine, "draft_saved")
    assert claim(engine, run_id) is None
    assert states(engine, other) == ("running", ["queued"])


def test_two_sessions_claim_different_items(engine: Engine) -> None:
    run_id, ids = make_run(engine, "queued", "queued")
    first, second = Session(engine), Session(engine)
    try:
        first.begin()
        second.begin()
        a = next_item(first, run_id)
        b = next_item(second, run_id)  # the first claim is not committed yet
        assert a is not None and b is not None
        assert (a.id, b.id) == (ids[0], ids[1])
        first.commit()
        second.commit()
    finally:
        first.close()
        second.close()
    assert states(engine, run_id) == ("running", ["running", "running"])


def test_run_moves_to_awaiting_approval_when_items_done_and_drafts_pending(
    engine: Engine,
) -> None:
    run_id, _ = make_run(engine, "draft_saved", "failed")
    assert settle(engine, run_id) is RunState.AWAITING_APPROVAL
    assert settle(engine, run_id) is RunState.AWAITING_APPROVAL  # settling again is a no-op
    assert states(engine, run_id)[0] == "awaiting_approval"


@pytest.mark.parametrize("waiting", ["draft_saved", "pending_approval", "approved"])
def test_every_undecided_draft_keeps_the_run_awaiting(engine: Engine, waiting: str) -> None:
    run_id, _ = make_run(engine, "committed", waiting)
    assert settle(engine, run_id) is RunState.AWAITING_APPROVAL


def test_run_is_done_when_every_item_is_terminal(engine: Engine) -> None:
    run_id, _ = make_run(engine, "committed", "rejected", "failed")
    assert settle(engine, run_id) is RunState.DONE
    assert settle(engine, run_id) is RunState.DONE


def test_awaiting_run_becomes_done(engine: Engine) -> None:
    run_id, _ = make_run(engine, "committed", run_state="awaiting_approval")
    assert settle(engine, run_id) is RunState.DONE


@pytest.mark.parametrize("busy", ["queued", "running"])
def test_run_stays_running_while_items_are_queued_or_running(engine: Engine, busy: str) -> None:
    run_id, _ = make_run(engine, "draft_saved", busy)
    assert settle(engine, run_id) is RunState.RUNNING
    assert states(engine, run_id)[0] == "running"


def test_stopped_run_stays_stopped(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued", "draft_saved", run_state="stopped")
    assert settle(engine, run_id) is RunState.STOPPED
    assert states(engine, run_id) == ("stopped", ["queued", "draft_saved"])


def test_run_without_items_is_done(engine: Engine) -> None:
    run_id, _ = make_run(engine)
    assert settle(engine, run_id) is RunState.DONE
