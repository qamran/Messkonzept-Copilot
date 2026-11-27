"""The work queue and run settling (MKC-15, design 8.2 and 8.4)."""

from sqlalchemy.orm import Session

from mkc.db.models import Item
from mkc.harness.states import RunState


def next_item(session: Session, run_id: int) -> Item | None:
    """Claim the oldest `queued` item of a `running` run and set it to `running`."""
    raise NotImplementedError


def settle_run(session: Session, run_id: int) -> RunState:
    """Derive the run's state from its items and store it if it changed."""
    raise NotImplementedError
