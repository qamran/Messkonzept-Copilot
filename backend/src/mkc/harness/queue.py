"""The work queue and run settling (MKC-15, design 8.2 and 8.4).

Neither function commits: the caller owns the transaction. Commit a claim before the first
model call, so no row lock is held across a model call.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from mkc.db.models import Item, Run
from mkc.harness.states import TERMINAL, ItemState, RunState, transition

BUSY = frozenset({ItemState.QUEUED, ItemState.RUNNING})
"""Items extraction has not finished with."""

UNDECIDED = frozenset({ItemState.DRAFT_SAVED, ItemState.PENDING_APPROVAL, ItemState.APPROVED})
"""Drafts that await a decision or a commit (decision 54)."""


def next_item(session: Session, run_id: int) -> Item | None:
    """Claim the oldest `queued` item of a `running` run and set it to `running`.

    `FOR UPDATE OF item SKIP LOCKED`: a concurrent claimer skips the locked item and takes
    the next one. The run row is not locked. `id` gives the order (rows inserted in one
    transaction share `created_at`).
    """
    statement = (
        select(Item)
        .join(Run, Run.id == Item.run_id)
        .where(
            Item.run_id == run_id,
            Item.state == ItemState.QUEUED.value,
            Run.state == RunState.RUNNING.value,
        )
        .order_by(Item.id)
        .limit(1)
        .with_for_update(skip_locked=True, of=Item)
    )
    item = session.scalars(statement).first()
    if item is None:
        return None
    item.state = transition(ItemState(item.state), ItemState.RUNNING).value
    session.flush()
    return item


def settle_run(session: Session, run_id: int) -> RunState:
    """Derive the run's state from its items and store it if it changed.

    - `running` while any item is queued or running
    - `awaiting_approval` when none is, but a draft awaits a decision or a commit
    - `done` when every item is committed, rejected or failed (also when there are none)

    A terminal run (`done`, `stopped`) is returned as it is.
    """
    run = session.scalars(select(Run).where(Run.id == run_id).with_for_update()).one()
    current = RunState(run.state)
    if current in TERMINAL:
        return current
    rows = session.scalars(select(Item.state).where(Item.run_id == run_id).distinct())
    present = {ItemState(state) for state in rows}
    if present & BUSY:
        target = RunState.RUNNING
    elif present & UNDECIDED:
        target = RunState.AWAITING_APPROVAL
    else:
        target = RunState.DONE
    if target is not current:
        run.state = transition(current, target).value
        session.flush()
    return RunState(run.state)
