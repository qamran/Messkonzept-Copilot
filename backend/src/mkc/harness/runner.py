"""Run a run in the mode it was created with (MKC-20.2, decision 60).

The executor and the CLI call `execute_run`. It reads `run.mode`, picks that mode's switches,
loads a `RunMemory` when the baseline needs one, builds the default registry for that mode
(unless a test passes its own) and calls `process_run`.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Run
from mkc.extraction.operations import DocumentOps
from mkc.harness.baseline import RunMemory
from mkc.harness.limits import Limits
from mkc.harness.loop import ItemOutcome, process_run
from mkc.harness.mode import SWITCHES, HarnessMode
from mkc.harness.registry import default_registry
from mkc.harness.tools import ToolRegistry, ToolTracer
from mkc.models.client import ModelClient


@dataclass(frozen=True)
class RunResult:
    """The outcomes of this attempt, and the baseline's memory (None in full mode)."""

    outcomes: list[ItemOutcome]
    memory: RunMemory | None


def execute_run(
    run_id: int,
    *,
    session: Session,
    sessions: sessionmaker[Session],
    client: ModelClient,
    limits: Limits,
    registry: ToolRegistry | None = None,
    tool_tracers: tuple[ToolTracer, ...] = (),
    documents: DocumentOps | None = None,
    **loop_kw: Any,
) -> RunResult:
    """`process_run` in the run's mode. `loop_kw` goes to `process_run` as it is. With
    `documents`, the default registry's document tools are real (`extract_text`,
    `extract_tables`, `render_region`; MKC-23, PR #215 finding 6); a passed `registry` is
    used as it is."""
    mode = HarnessMode(session.scalars(select(Run.mode).where(Run.id == run_id)).one())
    session.commit()
    switches = SWITCHES[mode]
    memory = None
    if not (switches.durable_queue and switches.durable_approvals):
        memory = RunMemory.load(session, run_id)
        session.commit()
    if registry is None:
        approvals = None if switches.durable_approvals else memory
        registry = default_registry(
            tool_tracers, sessions=sessions, approvals=approvals, documents=documents
        )
    outcomes = process_run(
        run_id,
        session=session,
        client=client,
        registry=registry,
        limits=limits,
        switches=switches,
        memory=memory,
        **loop_kw,
    )
    return RunResult(outcomes, memory)
