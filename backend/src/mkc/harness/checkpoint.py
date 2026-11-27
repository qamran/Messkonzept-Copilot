"""Turn checkpoints (MKC-16, design 8.3).

A turn is one model response plus the results of all its tool calls. `save_turn` stores only
a complete turn: every call paired with its result, in call order.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from mkc.db.models import Turn
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
    """Add the turn's row to `session` without committing; the caller commits.

    Raises `ValueError` unless the results answer the calls one to one, in call order.
    """
    call_ids = [call.id for call in turn.assistant.tool_calls]
    result_ids = [result["tool_call_id"] for result in turn.results]
    if call_ids != result_ids or len(set(call_ids)) != len(call_ids):
        raise ValueError(f"tool calls and results must pair: {call_ids} vs {result_ids}")
    session.add(
        Turn(
            item_id=turn.item_id,
            number=turn.number,
            assistant=turn.assistant.model_dump(mode="json"),
            tool_results=[
                {key: value for key, value in result.items() if key != "content"}
                for result in turn.results
            ],
            cost_eur=turn.cost_eur,
        )
    )
