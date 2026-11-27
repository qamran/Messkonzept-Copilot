"""What the baseline ("simple loop") keeps in memory instead of the database (MKC-20.2).

With `durable_queue` off, `process_run` serves the items in `RunMemory.todo`, keeps turns
and end states here, and writes the end states once, when the run ends (`write_report`). A
crash or SIGTERM before that writes nothing, so the next attempt restarts from zero. With
`durable_approvals` off, `save_draft` appends to `approvals` with no key: a second save adds
a second entry, and every entry dies with the process (decision 60).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mkc.db.models import Item
from mkc.harness.checkpoint import TurnRecord
from mkc.harness.limits import RunUsage
from mkc.harness.states import ItemState, transition
from mkc.harness.tools import ToolEnv

_OPEN = (ItemState.QUEUED.value, ItemState.RUNNING.value)


@dataclass
class RunMemory:
    """One baseline attempt at a run: its queue, turns, end states and pending approvals."""

    run_id: int
    todo: list[int] = field(default_factory=list)
    turns: dict[int, list[TurnRecord]] = field(default_factory=dict)
    ends: dict[int, tuple[ItemState, str | None]] = field(default_factory=dict)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)

    @classmethod
    def load(cls, session: Session, run_id: int) -> "RunMemory":
        """The run's open items (`queued` or `running`, in id order), read once."""
        rows = session.scalars(
            select(Item.id).where(Item.run_id == run_id, Item.state.in_(_OPEN)).order_by(Item.id)
        )
        return cls(run_id, todo=list(rows))

    def next(self) -> int | None:
        """Claim the next item in memory."""
        return self.todo.pop(0) if self.todo else None

    def add_turn(self, turn: TurnRecord) -> None:
        self.turns.setdefault(turn.item_id, []).append(turn)

    def item_usage(self, item_id: int) -> tuple[int, Decimal]:
        turns = self.turns.get(item_id, [])
        return len(turns), sum((t.cost_eur for t in turns), Decimal(0))

    def end(self, item_id: int, state: ItemState, reason: str | None) -> None:
        self.ends[item_id] = (state, reason)

    def usage(self) -> RunUsage:
        """Turns and cost in memory, wall time since this attempt began."""
        turns = [t for item in self.turns.values() for t in item]
        cost = sum((t.cost_eur for t in turns), Decimal(0))
        return RunUsage(len(turns), cost, time.monotonic() - self.started)

    def write_report(self, session: Session) -> None:
        """Write the items that ended: `queued -> running -> end`, with their reasons. Items
        not ended stay as they are. The caller fences and commits."""
        for item_id, (state, reason) in self.ends.items():
            item = session.get_one(Item, item_id)
            current = ItemState(item.state)
            if current is ItemState.QUEUED:
                current = transition(current, ItemState.RUNNING)
            item.state = transition(current, state).value
            item.failure_reason = reason
        self.ends.clear()
        session.flush()


def make_memory_save_draft(memory: RunMemory) -> Callable[[BaseModel, ToolEnv], Any]:
    """`save_draft` without a key or a row: every call appends one pending approval."""

    def save_draft(args: BaseModel, env: ToolEnv) -> Any:
        body = getattr(args, "draft")  # noqa: B009  (any args model with a `draft` field)
        memory.approvals.append(
            {
                "document_hash": env.document_hash,
                "concept_key": env.concept_key,
                "item_id": env.item_id,
                "body": body,
            }
        )
        return {"draft_id": f"memory-{len(memory.approvals)}"}

    return save_draft
