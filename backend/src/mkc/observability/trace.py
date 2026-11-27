"""The tracer (MKC-19, decision 59).

The harness already calls three kinds of hooks: `CallTrace` (each model call attempt),
`ToolTrace` (each tool call) and `StopEvent` (each stop). `Tracer` turns each into one
`TraceRecord` and writes it twice: one row in `run_log` (its own short session) and one
observation in Langfuse (the `Sink`). Each side is guarded on its own, so a tracing failure
never reaches the run.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

from sqlalchemy.orm import Session

from mkc.harness.limits import StopEvent
from mkc.harness.tools import ToolTrace
from mkc.models.client import CallTrace

log = logging.getLogger(__name__)

Kind = Literal["model", "tool", "stop", "outage"]

MAX_NAME = 100
"""A tool name is model-supplied: cut before it leaves the machine (finding 14#6)."""

MAX_ERROR = 500
"""Error text is cut to this many characters before it is stored or sent."""


@dataclass(frozen=True)
class TraceRecord:
    """One traced event: one `run_log` row and one Langfuse observation."""

    kind: Kind
    run_id: int
    name: str
    ok: bool
    item_id: int | None = None
    step: int | None = None
    error: str | None = None
    mode: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_eur: Decimal | None = None
    latency_ms: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class Sink(Protocol):
    """Where records go besides `run_log`: Langfuse (`mkc.observability.langfuse`)."""

    def send(self, record: TraceRecord, trace_id: str | None) -> None: ...

    def flush(self) -> None: ...


class Tracer:
    """One per worker process. Its hooks may be called from any thread."""

    def __init__(self, sessions: Callable[[], Session], sink: Sink | None = None) -> None:
        self._sessions = sessions
        self._sink = sink

    def start_run(self, run_id: int) -> str | None:
        """The run's trace id, set once if the run has none. None if it can't be read."""
        return None

    def span_model(self, trace: CallTrace) -> None:
        """Hook for `ModelClient(tracers=...)`."""

    def span_tool(self, trace: ToolTrace) -> None:
        """Hook for `ToolRegistry(tracers=...)`."""

    def span_stop(self, event: StopEvent) -> None:
        """Hook for `process_run(tracers=...)` and `stop_run`."""

    def outage(self, run_id: int, detail: str) -> None:
        """A database outage the worker waited out (finding 17#1: the durable record)."""

    def flush(self) -> None:
        """Send what the sink still holds; never raises."""
