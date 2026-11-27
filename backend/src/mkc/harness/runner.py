"""Run a run in its mode (MKC-20, decision 60)."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.baseline import RunMemory
from mkc.harness.limits import Limits
from mkc.harness.loop import ItemOutcome, process_run
from mkc.harness.registry import default_registry
from mkc.harness.tools import ToolRegistry
from mkc.models.client import ModelClient


@dataclass(frozen=True)
class RunResult:
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
    **loop_kw: Any,
) -> RunResult:
    registry = registry or default_registry(sessions=sessions)
    outcomes = process_run(
        run_id, session=session, client=client, registry=registry, limits=limits, **loop_kw
    )
    return RunResult(outcomes, None)
