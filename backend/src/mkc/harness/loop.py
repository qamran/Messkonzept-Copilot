"""The item loop (MKC-15, design 8.1 to 8.3).

Inside one item, the model drives the item tools until a `save_draft` call succeeds or the
item fails. `process_run` runs the queue: a failed item, or a draft that waits for approval,
never stops the next item (extraction never waits for approvals).

- One step is one model call. Each step writes one `turn` row and commits.
- The step that ends the item writes its turn row and the state change in one commit.
- Model and tool exceptions fail the item. Setup errors (`SETUP_ERRORS`), database errors and
  crashes propagate: the item stays `running`.
- Resume (MKC-16): `run_item` continues from the item's last complete turn
  (`load_resume_context`); `process_run` serves `running` items before queued ones.
- `run_item` commits whatever the caller's session has pending.
"""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Item
from mkc.harness.cache import ToolCache
from mkc.harness.checkpoint import INLINE_MAX_BYTES, TurnRecord, load_resume_context, save_turn
from mkc.harness.prompts import SYSTEM_PROMPT, TOOL_RESULT_CLOSE, task_message, wrap_tool_result
from mkc.harness.queue import next_item, resumable_item, settle_run
from mkc.harness.states import ItemState, transition
from mkc.harness.tools import ToolEnv, ToolRegistry
from mkc.models.client import ModelClient
from mkc.models.types import Message, ModelConfigError, ReplayMiss, Role, ToolCall

ROLE: Role = "extract_vision"
"""The extraction model in `models.yaml`."""

SETUP_ERRORS = (ModelConfigError, ReplayMiss)
"""Errors that would fail every item the same way (a missing key, a missing recording). They
propagate: the item stays `running` and the run is not settled, so it never reads as `done`.
MKC-18 turns them into a run stop."""

SAVE_TOOL = "save_draft"

__all__ = ["SYSTEM_PROMPT", "TOOL_RESULT_CLOSE", "task_message", "wrap_tool_result"]


@dataclass(frozen=True)
class ItemOutcome:
    """How an item ended. `reason` is set when `state` is `failed`."""

    item_id: int
    state: ItemState
    reason: str | None
    steps: int
    cost_eur: Decimal


class _ToolErrorEscaped(Exception):
    """A tool call raised out of `execute` or its result could not be serialised."""

    def __init__(self, error: Exception, results: list[dict[str, Any]]) -> None:
        super().__init__(str(error))
        self.error = error
        self.results = results


def run_item(
    item_id: int,
    *,
    session: Session,
    client: ModelClient,
    registry: ToolRegistry,
    max_steps: int,
    inline_max_bytes: int = INLINE_MAX_BYTES,
    code_version: str | None = None,
) -> ItemOutcome:
    """Run the model-driven tool loop for one claimed (`running`) item."""
    item = session.get_one(Item, item_id)
    if item.state != ItemState.RUNNING:
        raise ValueError(f"item {item_id} is not running (state {item.state!r})")
    env = ToolEnv(
        run_id=item.run_id,
        item_id=item.id,
        document_hash=item.document_hash,
        concept_key=item.concept_key,
    )
    specs = [tool.to_spec() for tool in registry.for_context("item")]
    cache = None
    if code_version is not None:
        cache = ToolCache(sessionmaker(bind=session.get_bind()), code_version)
    context = load_resume_context(session, item_id)
    messages = list(context.messages)
    session.commit()  # no transaction stays open across a model call

    cost = context.cost_eur
    for step in range(context.next_number, max_steps + 1):
        try:
            reply = client.chat_with_tools(ROLE, messages, specs)
        except SETUP_ERRORS:
            raise
        except Exception as error:
            reason = f"model_error: {type(error).__name__}"
            return _finish(
                session, item_id, None, ItemState.FAILED, reason, step, cost, inline_max_bytes
            )
        step_cost = Decimal(str(reply.usage.cost_eur))
        cost += step_cost
        calls = _with_ids(reply.tool_calls, step)
        assistant = Message(role="assistant", content=reply.text, tool_calls=calls)
        if not calls:
            turn = _turn(item_id, step, assistant, [], step_cost)
            return _finish(
                session,
                item_id,
                turn,
                ItemState.FAILED,
                "no_tool_call",
                step,
                cost,
                inline_max_bytes,
            )
        try:
            results, saved = _run_calls(registry, calls, env, cache)
        except _ToolErrorEscaped as escaped:
            answered = _answer_the_rest(calls, escaped)
            turn = _turn(item_id, step, assistant, answered, step_cost)
            reason = f"tool_error: {type(escaped.error).__name__}"
            return _finish(
                session, item_id, turn, ItemState.FAILED, reason, step, cost, inline_max_bytes
            )
        turn = _turn(item_id, step, assistant, results, step_cost)
        if saved:
            return _finish(
                session, item_id, turn, ItemState.DRAFT_SAVED, None, step, cost, inline_max_bytes
            )
        save_turn(session, turn, inline_max_bytes=inline_max_bytes)
        session.commit()
        messages.append(assistant)
        messages += [
            Message(role="tool", content=r["content"], tool_call_id=r["tool_call_id"])
            for r in results
        ]
    return _finish(
        session, item_id, None, ItemState.FAILED, "step_limit", max_steps, cost, inline_max_bytes
    )


def process_run(
    run_id: int,
    *,
    session: Session,
    client: ModelClient,
    registry: ToolRegistry,
    max_steps: int,
    inline_max_bytes: int = INLINE_MAX_BYTES,
    code_version: str | None = None,
) -> list[ItemOutcome]:
    """Claim and run items until the queue is empty, then settle the run.

    `inline_max_bytes` and `code_version` go to every `run_item` (the worker passes
    `Settings.turn_inline_max_bytes` and the build's commit, MKC-17).
    """
    outcomes = []
    while True:
        item = resumable_item(session, run_id) or next_item(session, run_id)
        item_id = None if item is None else item.id
        session.commit()  # the claim is durable before the first model call
        if item_id is None:
            break
        outcomes.append(
            run_item(
                item_id,
                session=session,
                client=client,
                registry=registry,
                max_steps=max_steps,
                inline_max_bytes=inline_max_bytes,
                code_version=code_version,
            )
        )
    settle_run(session, run_id)
    session.commit()
    return outcomes


def _with_ids(calls: list[ToolCall], step: int) -> tuple[ToolCall, ...]:
    """Every call gets an id no other call of the turn has: a tool message answers one id.

    An empty id becomes `call-<step>-<index>`; an id used twice becomes `<id>-<index>`. A
    unique id is kept; a new id that would clash with one in use gets `-<n>` appended.
    """
    seen = Counter(call.id for call in calls)
    used = {call.id for call in calls if call.id and seen[call.id] == 1}
    fixed = []
    for index, call in enumerate(calls):
        if call.id and seen[call.id] == 1:
            fixed.append(call)
            continue
        base = f"{call.id}-{index}" if call.id else f"call-{step}-{index}"
        new_id, n = base, 0
        while new_id in used:
            n += 1
            new_id = f"{base}-{n}"
        used.add(new_id)
        fixed.append(call.model_copy(update={"id": new_id}))
    return tuple(fixed)


NOT_RUN = "not run: an earlier call in this turn failed"


def _answer_the_rest(
    calls: tuple[ToolCall, ...], escaped: "_ToolErrorEscaped"
) -> list[dict[str, Any]]:
    """A stored turn pairs every call with a result, so a turn cut short by an escaped
    error answers the failing call and every call after it with an error."""
    error = escaped.error
    answered = list(escaped.results)
    for index, call in enumerate(calls[len(answered) :]):
        message = f"{type(error).__name__}: {error}"[:1000] if index == 0 else NOT_RUN
        payload = {"ok": False, "data": None,
                   "error": {"code": "tool_failed", "message": message}}  # fmt: skip
        answered.append({"tool_call_id": call.id, "name": call.name, "result": payload})
    return answered


def _run_calls(
    registry: ToolRegistry,
    calls: tuple[ToolCall, ...],
    env: ToolEnv,
    cache: ToolCache | None,
) -> tuple[list[dict[str, Any]], bool]:
    """Run every call of the turn. Returns the results and whether a save succeeded."""
    results: list[dict[str, Any]] = []
    saved = False
    for call in calls:
        try:
            result = registry.execute(call, "item", env, cache)
            payload = result.model_dump(mode="json")
            content = wrap_tool_result(call.name, payload)
        except SQLAlchemyError:
            raise  # like every database error: the item stays `running` and resumes
        except Exception as error:
            raise _ToolErrorEscaped(error, results) from error
        results.append(
            {"tool_call_id": call.id, "name": call.name, "result": payload, "content": content}
        )
        saved = saved or (call.name == SAVE_TOOL and result.ok)
    return results, saved


def _turn(
    item_id: int,
    number: int,
    assistant: Message,
    results: list[dict[str, Any]],
    cost: Decimal,
) -> TurnRecord:
    return TurnRecord(item_id, number, assistant, results, cost)


def _finish(
    session: Session,
    item_id: int,
    turn: TurnRecord | None,
    state: ItemState,
    reason: str | None,
    steps: int,
    cost: Decimal,
    inline_max_bytes: int,
) -> ItemOutcome:
    """Store the last turn (if any) and the item's end state in one commit."""
    item = session.get_one(Item, item_id)
    if turn is not None:
        save_turn(session, turn, inline_max_bytes=inline_max_bytes)
    item.state = transition(ItemState(item.state), state).value
    item.failure_reason = reason
    session.commit()
    return ItemOutcome(item_id, state, reason, steps, cost)
