"""Run and item states (design 8.2) and the one function that changes them (decision 54).

Every state write in the code goes through `transition`. The edge table is the design's;
the state columns have no CHECK constraint, so this function is the guard.
"""

from enum import StrEnum


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
    WAITING_FOR_DATABASE = "waiting_for_database"


class InvalidTransition(ValueError):
    """A state change that is not in the edge table."""


_I, _R = ItemState, RunState

EDGES: frozenset[tuple[ItemState, ItemState] | tuple[RunState, RunState]] = frozenset(
    {
        (_I.QUEUED, _I.RUNNING),  # queue: next_item
        (_I.RUNNING, _I.DRAFT_SAVED),  # loop: save_draft returned ok
        (_I.RUNNING, _I.FAILED),  # loop: model or tool error, no tool call, step cap
        (_I.DRAFT_SAVED, _I.PENDING_APPROVAL),  # harness: enqueue_approval (MKC-23)
        (_I.PENDING_APPROVAL, _I.APPROVED),  # human (MKC-29/30)
        (_I.PENDING_APPROVAL, _I.REJECTED),  # human (MKC-29/30)
        (_I.APPROVED, _I.COMMITTED),  # worker: commit_record (MKC-30)
        (_R.RUNNING, _R.AWAITING_APPROVAL),  # settle_run: drafts await a decision
        (_R.RUNNING, _R.DONE),  # settle_run: every item terminal
        (_R.RUNNING, _R.STOPPED),  # a run-level limit (MKC-18)
        (_R.AWAITING_APPROVAL, _R.DONE),  # settle_run
        (_R.RUNNING, _R.WAITING_FOR_DATABASE),  # worker: back after an outage (MKC-17)
        (_R.WAITING_FOR_DATABASE, _R.RUNNING),  # worker: claim_run (MKC-17)
    }
)

TERMINAL: frozenset[ItemState | RunState] = frozenset(
    {_I.COMMITTED, _I.REJECTED, _I.FAILED, _R.DONE, _R.STOPPED}
)


def transition[S: (ItemState, RunState)](current: S, target: S) -> S:
    """Return `target` if `current -> target` is an edge; raise `InvalidTransition` if not."""
    if type(current) is not type(target) or (current, target) not in EDGES:
        raise InvalidTransition(f"{current.value} -> {target.value}")
    return target
