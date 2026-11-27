"""Turn checkpoints (MKC-16, design 8.3).

A turn is one model response plus the results of all its tool calls. `save_turn` stores only
a complete turn: every call paired with its result, in call order.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mkc.db.models import Item, Turn
from mkc.harness.blobs import BlobStore, DbBlobStore
from mkc.harness.prompts import SYSTEM_PROMPT, earlier_turns, task_message, wrap_tool_result
from mkc.models.types import Message

INLINE_MAX_BYTES = 16384
"""A tool result whose JSON is larger is stored as a blob ref (`MKC_TURN_INLINE_MAX_BYTES`)."""


@dataclass(frozen=True)
class TurnRecord:
    """One complete turn. `results` hold `tool_call_id`, `name` and `result` per call."""

    item_id: int
    number: int
    assistant: Message
    results: list[dict[str, Any]]
    cost_eur: Decimal


@dataclass(frozen=True)
class ResumeContext:
    """Where an item continues: its messages, the next turn number, steps and cost so far."""

    messages: list[Message]
    next_number: int
    steps_done: int
    cost_eur: Decimal


def load_resume_context(
    session: Session, item_id: int, *, blobs: BlobStore | None = None
) -> ResumeContext:
    """The item task + a compact summary of earlier turns + the last complete turn.

    With no stored turn this is a fresh start. A turn in flight at a crash has no row, so it
    is not here and the loop re-requests it. The summary goes into the one user message:
    not every provider takes two user messages in a row.
    """
    item = session.get_one(Item, item_id)
    rows = list(session.scalars(select(Turn).where(Turn.item_id == item_id).order_by(Turn.number)))
    task = task_message(item.task)
    if len(rows) > 1:
        task += "\n" + earlier_turns([_summary(row) for row in rows[:-1]])
    messages = [Message(role="system", content=SYSTEM_PROMPT), Message(role="user", content=task)]
    if not rows:
        return ResumeContext(messages, next_number=1, steps_done=0, cost_eur=Decimal(0))
    last, store = rows[-1], blobs or DbBlobStore(session)
    messages.append(Message.model_validate(last.assistant))
    messages += [
        Message(
            role="tool",
            content=wrap_tool_result(entry["name"], stored_result(entry, store)),
            tool_call_id=entry["tool_call_id"],
        )
        for entry in last.tool_results
    ]
    cost = sum((row.cost_eur for row in rows), Decimal(0))
    return ResumeContext(messages, last.number + 1, last.number, cost)


def stored_result(entry: dict[str, Any], blobs: BlobStore) -> dict[str, Any]:
    """The full tool result of a stored turn entry, inline or from its blob ref."""
    if "result_ref" in entry:
        result: dict[str, Any] = json.loads(blobs.get(entry["result_ref"]["ref"]))
        return result
    stored: dict[str, Any] = entry["result"]
    return stored


def save_turn(
    session: Session,
    turn: TurnRecord,
    *,
    blobs: BlobStore | None = None,
    inline_max_bytes: int = INLINE_MAX_BYTES,
) -> None:
    """Add the turn's row to `session` without committing; the caller commits.

    Raises `ValueError` unless the results answer the calls one to one, in call order. A
    result whose JSON is over `inline_max_bytes` goes to `blobs` (default: `DbBlobStore` on
    the same session, so in the same transaction) and the row keeps `result_ref`.
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
                _stored(result, blobs or DbBlobStore(session), inline_max_bytes)
                for result in turn.results
            ],
            cost_eur=turn.cost_eur,
        )
    )


def _stored(result: dict[str, Any], blobs: BlobStore, inline_max_bytes: int) -> dict[str, Any]:
    entry = {key: value for key, value in result.items() if key not in ("content", "result")}
    data = json.dumps(result["result"], ensure_ascii=False, sort_keys=True).encode()
    if len(data) > inline_max_bytes:
        ok = result["result"]["ok"]
        entry["result_ref"] = {"ref": blobs.put(data), "bytes": len(data), "ok": ok}
    else:
        entry["result"] = result["result"]
    return entry


def _summary(row: Turn) -> dict[str, Any]:
    """One earlier turn: each call's tool, arguments and whether it worked."""
    calls = []
    for call, entry in zip(row.assistant["tool_calls"], row.tool_results, strict=True):
        result = entry.get("result") or entry["result_ref"]
        summary = {"tool": call["name"], "args": call["args"], "ok": result["ok"]}
        if result.get("error"):
            summary["error"] = result["error"]["code"]
        calls.append(summary)
    return {"turn": row.number, "calls": calls}
