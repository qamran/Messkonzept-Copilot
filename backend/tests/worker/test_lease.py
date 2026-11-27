"""MKC-17.1: one worker holds a run through a lease on the run row (decision 57)."""

from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select, text, update
from sqlalchemy.orm import Session

from mkc.db.models import Run, Turn
from mkc.harness.checkpoint import TurnRecord, save_turn
from mkc.models.types import Message
from mkc.worker.lease import LeaseLost, claim_run, fence, release_lease, renew_lease
from tests.harness.conftest import make_run

LEASE = 60.0


def claim(engine: Engine, owner: str) -> int | None:
    with Session(engine) as session, session.begin():
        run = claim_run(session, owner=owner, lease_seconds=LEASE)
        return None if run is None else run.id


def add_turns(engine: Engine, item_id: int, count: int) -> None:
    with Session(engine) as session, session.begin():
        for number in range(1, count + 1):
            session.add(_turn_row(item_id, number))


def _turn_row(item_id: int, number: int) -> Turn:
    return Turn(item_id=item_id, number=number, assistant={}, tool_results=[], cost_eur=0)


def turn_count(engine: Engine, item_id: int) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).where(Turn.item_id == item_id)) or 0


def lease(engine: Engine, run_id: int) -> tuple[str, str | None, bool]:
    """(state, owner, lease still valid by the database clock)."""
    with Session(engine) as session:
        run = session.get_one(Run, run_id)
        valid = session.scalar(select(Run.lease_expires_at > func.now()).where(Run.id == run_id))
        return run.state, run.lease_owner, bool(valid)


def expire(engine: Engine, run_id: int) -> None:
    with Session(engine) as session, session.begin():
        session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(lease_expires_at=func.now() - text("interval '1 second'"))
        )


def test_two_workers_only_one_claims(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    add_turns(engine, item_id, 2)
    first, second = Session(engine), Session(engine)
    try:
        first.begin()
        second.begin()
        won = claim_run(first, owner="w1", lease_seconds=LEASE)
        lost = claim_run(second, owner="w2", lease_seconds=LEASE)  # first not committed yet
        assert won is not None and won.id == run_id
        assert lost is None
        first.commit()
        second.rollback()
    finally:
        first.close()
        second.close()
    assert claim(engine, "w2") is None  # committed and not expired
    assert lease(engine, run_id) == ("running", "w1", True)
    assert turn_count(engine, item_id) == 2


def test_expired_lease_is_reclaimed(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    add_turns(engine, item_id, 2)
    assert claim(engine, "w1") == run_id
    expire(engine, run_id)
    assert claim(engine, "w2") == run_id
    assert lease(engine, run_id) == ("running", "w2", True)

    record = TurnRecord(item_id, 3, Message(role="assistant", content="late"), [], Decimal(0))
    with Session(engine) as session:  # the old worker tries to store its next turn
        save_turn(session, record)
        with pytest.raises(LeaseLost):
            fence(session, run_id, owner="w1")
        session.rollback()
    assert turn_count(engine, item_id) == 2

    with Session(engine) as session, session.begin():
        fence(session, run_id, owner="w2")  # the new owner may write
        save_turn(session, record)
    assert turn_count(engine, item_id) == 3


def test_a_worker_reclaims_its_own_lease(engine: Engine) -> None:
    run_id, _ = make_run(engine, "running")
    assert claim(engine, "w1") == run_id
    assert claim(engine, "w1") == run_id


@pytest.mark.parametrize("state", ["awaiting_approval", "done", "stopped"])
def test_only_running_or_waiting_runs_are_claimed(engine: Engine, state: str) -> None:
    make_run(engine, "draft_saved", run_state=state)
    assert claim(engine, "w1") is None


def test_the_oldest_free_run_is_claimed(engine: Engine) -> None:
    first, _ = make_run(engine, "queued")
    second, _ = make_run(engine, "queued")
    assert claim(engine, "w1") == first
    assert claim(engine, "w2") == second


def test_a_waiting_run_is_claimed_back_to_running(engine: Engine) -> None:
    run_id, _ = make_run(engine, "running", run_state="waiting_for_database")
    assert claim(engine, "w1") == run_id
    assert lease(engine, run_id) == ("running", "w1", True)


def test_only_the_owner_renews(engine: Engine) -> None:
    run_id, _ = make_run(engine, "running")
    assert claim(engine, "w1") == run_id
    expire(engine, run_id)
    with Session(engine) as session, session.begin():
        assert renew_lease(session, run_id, owner="w2", lease_seconds=LEASE) is False
        assert renew_lease(session, run_id, owner="w1", lease_seconds=LEASE) is True
    assert lease(engine, run_id) == ("running", "w1", True)


def test_only_the_owner_releases(engine: Engine) -> None:
    run_id, _ = make_run(engine, "running")
    assert claim(engine, "w1") == run_id
    with Session(engine) as session, session.begin():
        release_lease(session, run_id, owner="w2")
    assert lease(engine, run_id)[1] == "w1"
    with Session(engine) as session, session.begin():
        release_lease(session, run_id, owner="w1")
    assert lease(engine, run_id) == ("running", None, False)
    assert claim(engine, "w2") == run_id
