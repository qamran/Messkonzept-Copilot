"""The run lease (MKC-17.1, decision 57): one worker holds a run at a time.

Expiry uses the database clock (`now()`), never the pod's. No function commits; the caller
owns the transaction.
"""

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from mkc.db.models import Run
from mkc.harness.states import RunState, transition

CLAIMABLE = (RunState.RUNNING.value, RunState.WAITING_FOR_DATABASE.value)


class LeaseLost(Exception):
    """This worker no longer holds the run's lease."""


def _until(lease_seconds: float) -> object:
    return func.now() + func.make_interval(0, 0, 0, 0, 0, 0, lease_seconds)


def claim_run(
    session: Session, *, owner: str, lease_seconds: float, run_id: int | None = None
) -> Run | None:
    """Take the oldest `running` or `waiting_for_database` run whose lease is free, expired
    or already `owner`'s, and lease it to `owner` for `lease_seconds`.

    `FOR UPDATE SKIP LOCKED` covers a claim not yet committed; the lease condition covers a
    committed one. A `waiting_for_database` run goes back to `running`.
    """
    statement = (
        select(Run)
        .where(
            Run.state.in_(CLAIMABLE),
            or_(
                Run.lease_owner.is_(None),
                Run.lease_owner == owner,
                Run.lease_expires_at.is_(None),
                Run.lease_expires_at < func.now(),
            ),
        )
        .order_by(Run.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    run = session.scalars(statement).first()
    if run is None:
        return None
    if run.state == RunState.WAITING_FOR_DATABASE:
        run.state = transition(RunState(run.state), RunState.RUNNING).value
    run.lease_owner = owner
    run.lease_expires_at = _until(lease_seconds)  # type: ignore[assignment]
    session.flush()
    session.refresh(run, ["lease_expires_at"])
    return run


def renew_lease(session: Session, run_id: int, *, owner: str, lease_seconds: float) -> bool:
    """Extend `owner`'s lease. False: someone else holds the run now (the lease is lost)."""
    statement = (
        update(Run)
        .where(Run.id == run_id, Run.lease_owner == owner)
        .values(lease_expires_at=_until(lease_seconds))
        .returning(Run.id)
    )
    return session.execute(statement).first() is not None


def release_lease(session: Session, run_id: int, *, owner: str) -> None:
    """Free the run if `owner` holds it, so the next worker can take it at once."""
    session.execute(
        update(Run)
        .where(Run.id == run_id, Run.lease_owner == owner)
        .values(lease_owner=None, lease_expires_at=None)
    )


def mark_waiting(session: Session, run_id: int, *, owner: str) -> bool:
    """After an outage: set the run `running -> waiting_for_database` if `owner` still holds it
    or nobody took it over. False when the run moved on (another owner, another state)."""
    statement = (
        select(Run)
        .where(
            Run.id == run_id,
            Run.state == RunState.RUNNING.value,
            or_(
                Run.lease_owner == owner,
                Run.lease_owner.is_(None),
                Run.lease_expires_at < func.now(),
            ),
        )
        .with_for_update()
    )
    run = session.scalars(statement).first()
    if run is None:
        return False
    run.state = transition(RunState(run.state), RunState.WAITING_FOR_DATABASE).value
    session.flush()
    return True


def fence(session: Session, run_id: int, *, owner: str) -> None:
    """Lock the run row and raise `LeaseLost` unless `owner` holds a valid lease.

    Called in the transaction of every turn, item end state and item claim, so a worker whose
    lease was taken over can never write. The lock lasts until that (short) commit.
    """
    statement = (
        select(Run.id)
        .where(Run.id == run_id, Run.lease_owner == owner, Run.lease_expires_at > func.now())
        .with_for_update()
    )
    if session.execute(statement).first() is None:
        raise LeaseLost(f"run {run_id} is not leased to {owner}")
