"""Turn checkpoints (MKC-16, design 8.3).

A turn is one model response plus the results of all its tool calls. `save_turn` stores only
a complete turn: every call paired with its result, in call order.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from mkc.models.types import Message


@dataclass(frozen=True)
class TurnRecord:
    """One complete turn. `results` hold `tool_call_id`, `name` and `result` per call."""

    item_id: int
    number: int
    assistant: Message
    results: list[dict[str, Any]]
    cost_eur: Decimal


def save_turn(session: Session, turn: TurnRecord) -> None:
    """Add the turn's row to `session` without committing; the caller commits."""
    raise NotImplementedError
