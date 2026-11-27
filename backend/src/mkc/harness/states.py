"""Run and item states (design 8.2) and the one function that changes them (decision 54).

Every state write in the code goes through `transition`. The edge table is the design's;
the state columns have no CHECK constraint, so this function is the guard.
"""

from enum import StrEnum
from typing import TypeVar


class ItemState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DRAFT_SAVED = "draft_saved"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    COMMITTED = "committed"
    REJECTED = "rejected"
    FAILED = "failed"


class RunState(StrEnum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    DONE = "done"
    STOPPED = "stopped"


class InvalidTransition(ValueError):
    """A state change that is not in the edge table."""


EDGES: frozenset[tuple[ItemState, ItemState] | tuple[RunState, RunState]] = frozenset()

TERMINAL: frozenset[ItemState | RunState] = frozenset()

S = TypeVar("S", ItemState, RunState)


def transition(current: S, target: S) -> S:
    """Return `target` if `current -> target` is an edge; raise `InvalidTransition` if not."""
    raise InvalidTransition(f"{current.value} -> {target.value}")
