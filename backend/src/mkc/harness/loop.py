"""The item loop (MKC-15, design 8.1 to 8.3).

Inside one item, the model drives the item tools until a `save_draft` call succeeds or the
item fails. `process_run` runs the queue: a failed item, or a draft that waits for approval,
never stops the next item (extraction never waits for approvals).

- One step is one model call. Each step writes one `turn` row and commits.
- The step that ends the item writes its turn row and the state change in one commit.
- Model and tool exceptions fail the item. Transient model errors are retried (`call_model`);
  when retries run out, or on a setup error (`SETUP_ERRORS`), the run stops (MKC-18). Database
  errors and crashes propagate: the item stays `running`.
- Resume (MKC-16): `run_item` continues from the item's last complete turn
  (`load_resume_context`); `process_run` serves `running` items before queued ones.
- `run_item` commits whatever the caller's session has pending.
- The worker (MKC-17) passes `should_stop`, checked after each committed turn and before each
  claim (the item stays `running`), and `fence`, called before each commit; it raises when
  the worker lost its lease.
"""

import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import partial
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Item, Turn
from mkc.harness.baseline import RunMemory
from mkc.harness.cache import ToolCache
from mkc.harness.checkpoint import (
    INLINE_MAX_BYTES,
    ResumeContext,
    TurnRecord,
    load_resume_context,
    save_turn,
)
from mkc.harness.faults import FaultInjector
from mkc.harness.limits import (
    Limits,
    RunUsage,
    StopEvent,
    StopReason,
    StopTracer,
    emit,
    run_limit_hit,
    run_usage,
    start_clock,
    stop_run,
)
from mkc.harness.mode import SWITCHES, HarnessMode, Switches
from mkc.harness.prompts import (
    REPROMPT,
    SYSTEM_PROMPT,
    TOOL_RESULT_CLOSE,
    task_message,
    wrap_tool_result,
)
from mkc.harness.queue import has_work, next_item, resumable_item, settle_run
from mkc.harness.retry import RetriesExhausted, RetryInterrupted, call_model
from mkc.harness.states import ItemState, transition
from mkc.harness.tools import ToolEnv, ToolRegistry
from mkc.models.client import ModelClient, TraceScope
from mkc.models.types import Message, ModelConfigError, ModelReply, ReplayMiss, Role, ToolCall

ROLE: Role = "extract_vision"
"""The extraction model in `models.yaml`."""

SETUP_ERRORS = (ModelConfigError, ReplayMiss)
"""Errors that would fail every item the same way (a missing key or setting, a missing
recording, a refused key: `ModelAuthError` is a `ModelConfigError`). They stop the run with
`setup_error` (MKC-18, decision 58); the item keeps its place, so the run never reads `done`."""

SAVE_TOOL = "save_draft"

FULL = SWITCHES[HarnessMode.FULL]

INTERRUPTED = "interrupted"
"""`ItemOutcome.reason` of an item left `running` because `should_stop` said so."""

__all__ = ["SYSTEM_PROMPT", "TOOL_RESULT_CLOSE", "task_message", "wrap_tool_result"]


def _never() -> bool:
    return False


def _unfenced(session: Session) -> None:
    return None


def _sleep(seconds: float) -> bool:
    time.sleep(seconds)
    return False


@dataclass(frozen=True)
class ItemOutcome:
    """How an item ended. `reason` is set when `state` is `failed`, and is `interrupted` when
    the item was left `running` by `should_stop`."""

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
    limits: Limits,
    inline_max_bytes: int = INLINE_MAX_BYTES,
    code_version: str | None = None,
    should_stop: Callable[[], bool] = _never,
    fence: Callable[[Session], None] = _unfenced,
    tracers: Sequence[StopTracer] = (),
    sleep: Callable[[float], bool] = _sleep,
    switches: Switches = FULL,
    memory: RunMemory | None = None,
    faults: FaultInjector | None = None,
) -> ItemOutcome:
    """Run the model-driven tool loop for one claimed item: `running` in the database, or,
    with `durable_queue` off, claimed in `memory` (MKC-20, decision 60)."""
    item = session.get_one(Item, item_id)
    queue = _memory_queue(switches, memory)
    if queue is None and item.state != ItemState.RUNNING:
        raise ValueError(f"item {item_id} is not running (state {item.state!r})")
    env = ToolEnv(
        run_id=item.run_id,
        item_id=item.id,
        document_hash=item.document_hash,
        concept_key=item.concept_key,
    )
    ctx = _Ctx(session, item_id, item.run_id, inline_max_bytes, fence, tracers, queue)
    specs = [tool.to_spec() for tool in registry.for_context("item")]
    cache = None
    if code_version is not None and switches.tool_cache:
        cache = ToolCache(sessionmaker(bind=session.get_bind()), code_version)
    if switches.checkpoints:
        context = load_resume_context(session, item_id)
    else:  # every attempt starts from the task
        task = [Message(role="system", content=SYSTEM_PROMPT),
                Message(role="user", content=task_message(item.task))]  # fmt: skip
        context = ResumeContext(task, next_number=1, steps_done=0, cost_eur=Decimal(0))
    messages = list(context.messages)
    reprompts = context.no_call_turns  # re-prompts already used (decision 58)
    failures = Counter(context.tool_failures)
    session.commit()  # no transaction stays open across a model call

    cost = context.cost_eur
    for step in range(context.next_number, limits.max_steps_item + 1):
        hit = _run_limit(session, ctx.run_id, item_id, limits, fence, tracers, queue)
        if hit is not None:
            return ItemOutcome(item_id, ItemState.RUNNING, hit.value, step - 1, cost)
        scope = TraceScope(ctx.run_id, item_id, step)
        model_call: Callable[[], ModelReply] = partial(
            client.chat_with_tools, ROLE, tuple(messages), specs, scope=scope
        )
        if faults is not None:
            model_call = faults.model(model_call)
        try:
            reply = call_model(
                model_call,
                limits=limits,
                sleep=sleep,
                should_stop=should_stop,
            )
        except RetryInterrupted:
            return ItemOutcome(item_id, ItemState.RUNNING, INTERRUPTED, step - 1, cost)
        except RetriesExhausted as exhausted:
            last = str(exhausted.__cause__)[:300]
            return ctx.stop(StopReason.MODEL_UNAVAILABLE, last, step - 1, cost)
        except SETUP_ERRORS as error:
            return ctx.stop(StopReason.SETUP_ERROR, type(error).__name__, step - 1, cost)
        except Exception as error:
            return ctx.fail(None, StopReason.MODEL_ERROR, step, cost, type(error).__name__)
        step_cost = Decimal(str(reply.usage.cost_eur))
        cost += step_cost
        calls = _with_ids(reply.tool_calls, step)
        assistant = Message(role="assistant", content=reply.text, tool_calls=calls)
        if not calls:
            turn = _turn(item_id, step, assistant, [], step_cost)
            if reprompts >= limits.max_reprompts:
                return ctx.fail(turn, StopReason.MALFORMED_OUTPUT, step, cost)
            reprompts += 1
            ctx.store(turn)
            if should_stop():
                return ItemOutcome(item_id, ItemState.RUNNING, INTERRUPTED, step, cost)
            messages += [assistant, Message(role="user", content=REPROMPT)]
            continue
        try:
            results, saved = _run_calls(registry, calls, replace(env, step=step), cache, faults)
        except _ToolErrorEscaped as escaped:
            answered = _answer_the_rest(calls, escaped)
            turn = _turn(item_id, step, assistant, answered, step_cost)
            name = type(escaped.error).__name__
            return ctx.fail(turn, StopReason.TOOL_ERROR, step, cost, name)
        turn = _turn(item_id, step, assistant, results, step_cost)
        if saved:
            return ctx.finish(turn, ItemState.DRAFT_SAVED, None, step, cost)
        failures.update(r["name"] for r in results if not r["result"]["ok"])
        over = [name for name, n in failures.items() if n > limits.max_retries_tool]
        if over:
            return ctx.fail(turn, StopReason.TOOL_RETRIES, step, cost, over[0])
        ctx.store(turn)
        if should_stop():
            return ItemOutcome(item_id, ItemState.RUNNING, INTERRUPTED, step, cost)
        messages.append(assistant)
        messages += [
            Message(role="tool", content=r["content"], tool_call_id=r["tool_call_id"])
            for r in results
        ]
    return ctx.fail(None, StopReason.STEP_LIMIT, limits.max_steps_item, cost)


def process_run(
    run_id: int,
    *,
    session: Session,
    client: ModelClient,
    registry: ToolRegistry,
    limits: Limits,
    inline_max_bytes: int = INLINE_MAX_BYTES,
    code_version: str | None = None,
    should_stop: Callable[[], bool] = _never,
    fence: Callable[[Session], None] = _unfenced,
    tracers: Sequence[StopTracer] = (),
    sleep: Callable[[float], bool] = _sleep,
    switches: Switches = FULL,
    memory: RunMemory | None = None,
    faults: FaultInjector | None = None,
) -> list[ItemOutcome]:
    """Claim and run items until the queue is empty, then settle the run.

    `inline_max_bytes` and `code_version` go to every `run_item` (the worker passes
    `Settings.turn_inline_max_bytes` and the build's commit, MKC-17). When `should_stop`
    ends the run early, the run is not settled.

    With `durable_queue` off (baseline, decision 60), the items come from `memory` and nothing
    is written until the run settles or stops; then `memory.write_report` writes the ended
    items. An interrupted baseline run writes nothing and starts again from zero.
    """
    outcomes: list[ItemOutcome] = []
    queue = _memory_queue(switches, memory)
    loop_kw: dict[str, Any] = {
        "session": session, "client": client, "registry": registry, "limits": limits,
        "inline_max_bytes": inline_max_bytes, "code_version": code_version,
        "should_stop": should_stop, "fence": fence, "tracers": tracers, "sleep": sleep,
        "switches": switches, "memory": memory, "faults": faults,
    }  # fmt: skip
    if queue is not None:
        while not should_stop():
            if not queue.todo:
                queue.write_report(session)
                return _settle(session, run_id, fence, outcomes)
            if _run_limit(session, run_id, None, limits, fence, tracers, queue) is not None:
                return outcomes
            item_id = queue.next()
            assert item_id is not None
            outcomes.append(run_item(item_id, **loop_kw))
            if faults is not None:
                faults.item_ended(outcomes[-1])
            if outcomes[-1].state is ItemState.RUNNING:
                return outcomes
        return outcomes
    start_clock(session, run_id)
    fence(session)
    session.commit()
    while True:
        if should_stop():
            return outcomes
        if not has_work(session, run_id):
            break  # nothing left: settle, even when the last turn reached a limit (MKC-19.1)
        if _run_limit(session, run_id, None, limits, fence, tracers) is not None:
            return outcomes
        item = resumable_item(session, run_id)
        resumed = item is not None
        if item is None:
            item = next_item(session, run_id)
        else:
            item.attempts_without_progress += 1  # back to 0 with the next stored turn
        item_id = None if item is None else item.id
        attempts = 0 if item is None else item.attempts_without_progress
        fence(session)
        session.commit()  # the claim is durable before the first model call
        if item_id is None:
            break
        if resumed and attempts > limits.max_resumes_item:
            ctx = _Ctx(session, item_id, run_id, inline_max_bytes, fence, tracers)
            outcomes.append(ctx.fail(None, StopReason.RESUME_LIMIT, None, None))
            continue
        outcomes.append(run_item(item_id, **loop_kw))
        if faults is not None:
            faults.item_ended(outcomes[-1])
        if outcomes[-1].state is ItemState.RUNNING:
            return outcomes
    settle_run(session, run_id)
    session.commit()
    return outcomes


def _memory_queue(switches: Switches, memory: RunMemory | None) -> RunMemory | None:
    """The in-memory queue when `durable_queue` is off; None when the database is the queue."""
    if switches.durable_queue:
        return None
    if memory is None:
        raise ValueError("durable_queue off needs a RunMemory")
    return memory


def _settle(
    session: Session, run_id: int, fence: Callable[[Session], None], outcomes: list[ItemOutcome]
) -> list[ItemOutcome]:
    settle_run(session, run_id)
    fence(session)
    session.commit()
    return outcomes


def _usage(session: Session, run_id: int, queue: RunMemory | None) -> RunUsage:
    return run_usage(session, run_id) if queue is None else queue.usage()


def _stop(
    session: Session,
    run_id: int,
    reason: StopReason,
    *,
    queue: RunMemory | None,
    fence: Callable[[Session], None],
    tracers: Sequence[StopTracer],
    item_id: int | None,
    detail: str | None = None,
) -> bool:
    """Stop the run; a baseline run writes its ended items first, in the same commit."""
    usage = _usage(session, run_id, queue)
    if queue is not None:
        queue.write_report(session)
    event = stop_run(session, run_id, reason, usage=usage, fence=fence, tracers=tracers,
                     item_id=item_id, detail=detail)  # fmt: skip
    return event is not None


def _run_limit(
    session: Session,
    run_id: int,
    item_id: int | None,
    limits: Limits,
    fence: Callable[[Session], None],
    tracers: Sequence[StopTracer],
    queue: RunMemory | None = None,
) -> StopReason | None:
    """Check the run limits before a model call or a claim; stop the run if one is hit.

    Usage comes from the database, or from `queue` in baseline. Returns the reason only when
    this call stopped the run. Ends its transaction either way, so none stays open across the
    model call."""
    hit = run_limit_hit(_usage(session, run_id, queue), limits)
    if hit is None:
        session.commit()
        return None
    stopped = _stop(session, run_id, hit, queue=queue, fence=fence, tracers=tracers,
                    item_id=item_id)  # fmt: skip
    return hit if stopped else None


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
    faults: FaultInjector | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Run every call of the turn. Returns the results and whether a save succeeded."""
    results: list[dict[str, Any]] = []
    saved = False
    for call in calls:
        try:
            injected = None if faults is None else faults.tool(call)
            result = injected or registry.execute(call, "item", env, cache)
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


@dataclass(frozen=True)
class _Ctx:
    """What storing a turn and ending an item need."""

    session: Session
    item_id: int
    run_id: int
    inline_max_bytes: int
    fence: Callable[[Session], None]
    tracers: Sequence[StopTracer]
    memory: RunMemory | None = None
    """The baseline's in-memory queue (durable queue off), else None."""

    def store(self, turn: TurnRecord) -> None:
        """Store a turn that does not end the item; a stored turn is progress (decision 58)."""
        if self.memory is not None:
            self.memory.add_turn(turn)
            return
        save_turn(self.session, turn, inline_max_bytes=self.inline_max_bytes)
        self.session.execute(
            update(Item).where(Item.id == self.item_id).values(attempts_without_progress=0)
        )
        self.fence(self.session)
        self.session.commit()

    def stop(self, reason: StopReason, detail: str, steps: int, cost: Decimal) -> ItemOutcome:
        """Stop the run (decision 58); this item keeps its place and its checkpoint."""
        _stop(self.session, self.run_id, reason, queue=self.memory, fence=self.fence,
              tracers=self.tracers, item_id=self.item_id, detail=detail)  # fmt: skip
        return ItemOutcome(self.item_id, ItemState.RUNNING, reason.value, steps, cost)

    def fail(
        self,
        turn: TurnRecord | None,
        reason: StopReason,
        steps: int | None,
        cost: Decimal | None,
        detail: str | None = None,
    ) -> ItemOutcome:
        return self.finish(turn, ItemState.FAILED, reason, steps, cost, detail)

    def finish(
        self,
        turn: TurnRecord | None,
        state: ItemState,
        reason: StopReason | None,
        steps: int | None,
        cost: Decimal | None,
        detail: str | None = None,
    ) -> ItemOutcome:
        """Store the last turn (if any) and the item's end state in one commit. A failure is
        also a `StopEvent` with the item's stored turns and their cost; with `steps` and
        `cost` None the outcome takes those stored values too."""
        if self.memory is not None:
            return self._finish_in_memory(self.memory, turn, state, reason, steps, cost, detail)
        session = self.session
        turns, spent = session.execute(  # before any write: no autoflush splits the commit
            select(func.count(Turn.id), func.coalesce(func.sum(Turn.cost_eur), 0)).where(
                Turn.item_id == self.item_id
            )
        ).one()
        turns, spent = int(turns), Decimal(spent)
        item = session.get_one(Item, self.item_id)
        if turn is not None:
            save_turn(session, turn, inline_max_bytes=self.inline_max_bytes)
            item.attempts_without_progress = 0
            turns, spent = turns + 1, spent + turn.cost_eur
        stored = None
        if reason is not None:
            stored = f"{reason.value}: {detail}" if detail else reason.value
        item.state = transition(ItemState(item.state), state).value
        item.failure_reason = stored
        self.fence(session)
        session.commit()
        if reason is not None:
            event = StopEvent("item", self.run_id, self.item_id, reason, detail, turns, spent)
            emit(self.tracers, event)
        steps = turns if steps is None else steps
        cost = spent if cost is None else cost
        return ItemOutcome(self.item_id, state, stored, steps, cost)

    def _finish_in_memory(
        self,
        memory: RunMemory,
        turn: TurnRecord | None,
        state: ItemState,
        reason: StopReason | None,
        steps: int | None,
        cost: Decimal | None,
        detail: str | None,
    ) -> ItemOutcome:
        """`finish` with the durable queue off: the end state waits in memory for the report."""
        if turn is not None:
            memory.add_turn(turn)
        turns, spent = memory.item_usage(self.item_id)
        stored = None
        if reason is not None:
            stored = f"{reason.value}: {detail}" if detail else reason.value
        memory.end(self.item_id, state, stored)
        if reason is not None:
            event = StopEvent("item", self.run_id, self.item_id, reason, detail, turns, spent)
            emit(self.tracers, event)
        steps = turns if steps is None else steps
        cost = spent if cost is None else cost
        return ItemOutcome(self.item_id, state, stored, steps, cost)
