"""Limits and stop reasons (MKC-18, design 8.5, decision 58).

- Item reasons go into `item.failure_reason` and the item goes `failed`.
- Run reasons go into `run.stop_reason` and the run goes `stopped`; its items stay as they
  are (the item in flight keeps its checkpoint, queued items stay queued).
- Every stop, of either scope, is also a `StopEvent` for the trace hooks.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from sqlalchemy import extract, func, select, update
from sqlalchemy.orm import Session

from mkc.config import Settings
from mkc.db.models import Item, Run, Turn
from mkc.harness.states import RunState, transition

log = logging.getLogger(__name__)

Scope = Literal["run", "item"]


class StopReason(StrEnum):
    # item level: the item fails
    STEP_LIMIT = "step_limit"
    TOOL_RETRIES = "tool_retries"
    MALFORMED_OUTPUT = "malformed_output"
    RESUME_LIMIT = "resume_limit"
    MODEL_ERROR = "model_error"  # stored as `model_error: <class>`
    TOOL_ERROR = "tool_error"  # stored as `tool_error: <class>`
    # run level: the run stops
    RUN_STEP_LIMIT = "run_step_limit"
    WALL_TIME = "wall_time"
    COST_LIMIT = "cost_limit"
    SETUP_ERROR = "setup_error"
    MODEL_UNAVAILABLE = "model_unavailable"

    @property
    def scope(self) -> Scope:
        return "run" if self in _RUN_REASONS else "item"


_RUN_REASONS = frozenset(
    {
        StopReason.RUN_STEP_LIMIT,
        StopReason.WALL_TIME,
        StopReason.COST_LIMIT,
        StopReason.SETUP_ERROR,
        StopReason.MODEL_UNAVAILABLE,
    }
)


@dataclass(frozen=True)
class Limits:
    """Every limit of the harness. The defaults are the settings' defaults (plan of MKC-18).

    `max_reprompts` (1, feature 22) has no setting; MKC-20's baseline mode sets it to 0.
    """

    max_steps_item: int = 12
    max_steps_run: int = 300
    max_wall_s: float = 7200.0
    max_cost_eur: Decimal = Decimal("3.00")
    max_retries_tool: int = 3
    max_retries_model: int = 4
    max_reprompts: int = 1
    max_resumes_item: int = 3
    backoff_base_s: float = 2.0
    backoff_max_s: float = 60.0
    turn_timeout_s: float = 180.0

    def __post_init__(self) -> None:
        positive = ("max_steps_item", "max_steps_run", "max_wall_s", "max_cost_eur",
                    "backoff_base_s", "turn_timeout_s")  # fmt: skip
        for f in fields(self):
            value = getattr(self, f.name)
            if value < 0 or (f.name in positive and value == 0):
                raise ValueError(
                    f"Limits.{f.name} must be {'> 0' if f.name in positive else '>= 0'}"
                )
        if self.backoff_max_s < self.backoff_base_s:
            raise ValueError("Limits.backoff_max_s must be at least backoff_base_s")

    @classmethod
    def from_settings(cls, settings: Settings) -> "Limits":
        return cls(
            max_steps_item=settings.item_max_steps,
            max_steps_run=settings.run_max_steps,
            max_wall_s=settings.run_max_wall_seconds,
            max_cost_eur=settings.run_max_cost_eur,
            max_retries_tool=settings.tool_max_retries,
            max_retries_model=settings.model_max_retries,
            max_resumes_item=settings.item_max_resumes,
            backoff_base_s=settings.model_backoff_base_seconds,
            backoff_max_s=settings.model_backoff_max_seconds,
            turn_timeout_s=settings.turn_timeout_seconds,
        )


@dataclass(frozen=True)
class StopEvent:
    """One stop, as the trace hooks see it (like `CallTrace` and `ToolTrace`; MKC-19 sends it
    to Langfuse and `run_log`). `steps` and `cost_eur` are the run's for a run stop and the
    item's for an item stop. `detail` is extra text, e.g. the error class."""

    scope: Scope
    run_id: int
    item_id: int | None
    reason: StopReason
    detail: str | None
    steps: int
    cost_eur: Decimal


StopTracer = Callable[[StopEvent], None]


@dataclass(frozen=True)
class RunUsage:
    """What a run has used, counted from the database: stored turns, their cost, wall time."""

    steps: int
    cost_eur: Decimal
    wall_s: float


def run_limit_hit(usage: RunUsage, limits: Limits) -> StopReason | None:
    """The run limit `usage` has reached, checked before a model call; None if none."""
    if usage.steps >= limits.max_steps_run:
        return StopReason.RUN_STEP_LIMIT
    if usage.cost_eur >= limits.max_cost_eur:
        return StopReason.COST_LIMIT
    if usage.wall_s >= limits.max_wall_s:
        return StopReason.WALL_TIME
    return None


def start_clock(session: Session, run_id: int) -> None:
    """Set `run.started_at` to the database's `now()` unless it is set. The caller commits."""
    session.execute(
        update(Run).where(Run.id == run_id, Run.started_at.is_(None)).values(started_at=func.now())
    )


def run_usage(session: Session, run_id: int) -> RunUsage:
    """The run's stored turns, their cost and the seconds since `started_at` (0 if unset)."""
    steps, cost = session.execute(
        select(func.count(Turn.id), func.coalesce(func.sum(Turn.cost_eur), 0))
        .join(Item, Item.id == Turn.item_id)
        .where(Item.run_id == run_id)
    ).one()
    wall = session.scalar(
        select(func.coalesce(extract("epoch", func.now() - Run.started_at), 0)).where(
            Run.id == run_id
        )
    )
    return RunUsage(steps=int(steps), cost_eur=Decimal(cost), wall_s=float(wall or 0))


def stop_run(
    session: Session,
    run_id: int,
    reason: StopReason,
    *,
    usage: RunUsage,
    fence: Callable[[Session], None],
    tracers: Sequence[StopTracer] = (),
    item_id: int | None = None,
    detail: str | None = None,
) -> StopEvent | None:
    """The one writer of a run stop: `running -> stopped` with `stop_reason`, fenced and
    committed, then the trace. Its items are left as they are. A run that is not `running`
    (stopped, done, awaiting approval) is left alone: None."""
    if reason.scope != "run":
        raise ValueError(f"{reason} is not a run stop reason")
    run = session.scalars(select(Run).where(Run.id == run_id).with_for_update()).one()
    if run.state != RunState.RUNNING:
        session.commit()
        return None
    run.state = transition(RunState(run.state), RunState.STOPPED).value
    run.stop_reason = reason.value
    fence(session)
    session.commit()
    event = StopEvent("run", run_id, item_id, reason, detail, usage.steps, usage.cost_eur)
    emit(tracers, event)
    return event


def emit(tracers: Sequence[StopTracer], event: StopEvent) -> None:
    """Log the stop and call every trace hook; a failing hook is logged, never raised."""
    where = f"run {event.run_id}" if event.scope == "run" else f"item {event.item_id}"
    verb = "stopped" if event.scope == "run" else "failed"
    log.warning(
        "%s %s: %s%s (steps %s, cost %s EUR)",
        where,
        verb,
        event.reason.value,
        f" ({event.detail})" if event.detail else "",
        event.steps,
        event.cost_eur,
    )
    for tracer in tracers:
        try:
            tracer(event)
        except Exception:
            log.exception("stop trace hook failed for %s", where)
