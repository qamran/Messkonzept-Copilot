"""The tracer (MKC-19, decision 59).

The harness already calls three kinds of hooks: `CallTrace` (each model call attempt),
`ToolTrace` (each tool call) and `StopEvent` (each stop); `retrieve` calls a fourth,
`RetrievalTrace` (MKC-50, decision 80). `Tracer` turns each into one
`TraceRecord` and writes it twice: one row in `run_log` (its own short session) and one
observation in Langfuse (the `Sink`). Each side is guarded on its own, so a tracing failure
never reaches the run.
"""

import logging
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from mkc.db.models import Run, RunLog
from mkc.harness.limits import StopEvent, StopReason
from mkc.harness.tools import ToolTrace
from mkc.models.client import CallTrace
from mkc.rag.retriever import RetrievalTrace

log = logging.getLogger(__name__)

Kind = Literal["model", "tool", "stop", "outage", "retrieval"]

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
    public_error: str | None = None
    """What the sink may send of the error: the error class (and HTTP status), a tool error
    code, or a tool name cut to `MAX_NAME`. Never the text, which can quote a prompt or a
    model reply; `error` keeps that for `run_log` (MKC-20.5, finding 19#1)."""


class Sink(Protocol):
    """Where records go besides `run_log`: Langfuse (`mkc.observability.langfuse`)."""

    def send(self, record: TraceRecord, trace_id: str | None) -> None: ...

    def flush(self) -> None: ...


class Tracer:
    """One per worker process. Its hooks may be called from any thread (model hooks fire on
    the `mkc-model-call` thread), so each write opens its own short session."""

    def __init__(self, sessions: Callable[[], Session], sink: Sink | None = None) -> None:
        self._sessions = sessions
        self._sink = sink
        self._trace_ids: dict[int, str] = {}
        self._lock = threading.Lock()

    def start_run(self, run_id: int) -> str | None:
        """The run's trace id, set once if the run has none (a resume by another worker reuses
        it). None if the database can't be reached: the run goes on untraced."""
        try:
            with self._sessions() as session:
                session.execute(
                    update(Run)
                    .where(Run.id == run_id, Run.trace_id.is_(None))
                    .values(trace_id=uuid.uuid4().hex)
                )
                found = session.scalar(select(Run.trace_id).where(Run.id == run_id))
                session.commit()
        except Exception:
            log.exception("run %s: trace id not set; tracing goes on without it", run_id)
            return None
        if found is not None:
            with self._lock:
                self._trace_ids[run_id] = found
        return found

    def span_model(self, trace: CallTrace) -> None:
        """Hook for `ModelClient(tracers=...)`: one record per attempt."""
        self._guarded("model", self._span_model, trace)

    def span_tool(self, trace: ToolTrace) -> None:
        """Hook for `ToolRegistry(tracers=...)`."""
        self._guarded("tool", self._span_tool, trace)

    def span_stop(self, event: StopEvent) -> None:
        """Hook for `process_run(tracers=...)` and `stop_run`."""
        self._guarded("stop", self._span_stop, event)

    def _guarded(self, kind: str, build: Callable[[Any], None], event: Any) -> None:
        """Build and record inside one guard: a hook never raises into the loop (19#3)."""
        try:
            build(event)
        except Exception as error:
            log.warning("%s trace not recorded: %s", kind, type(error).__name__)

    def _span_model(self, trace: CallTrace) -> None:
        if trace.scope is None:
            return  # not part of a run: no trace to join
        usage = trace.usage
        self._record(
            TraceRecord(
                kind="model",
                run_id=trace.scope.run_id,
                item_id=trace.scope.item_id,
                step=trace.scope.step,
                name=trace.model_id,
                ok=trace.error is None,
                error=_cut(trace.error),
                public_error=_error_class(trace.error),
                mode=trace.mode,
                input_tokens=None if usage is None else usage.input_tokens,
                output_tokens=None if usage is None else usage.output_tokens,
                cost_eur=None if usage is None else _eur(usage.cost_eur),
                latency_ms=trace.latency_ms,
                detail={"role": trace.role, "method": trace.method},
            )
        )

    def _span_tool(self, trace: ToolTrace) -> None:
        if trace.run_id is None:
            return
        self._record(
            TraceRecord(
                kind="tool",
                run_id=trace.run_id,
                item_id=trace.item_id,
                step=trace.step,
                name=trace.tool[:MAX_NAME],
                ok=trace.ok,
                error=trace.error_code,
                public_error=trace.error_code,
                latency_ms=trace.latency_ms,
                detail={"ctx": trace.ctx, "refused": trace.refused, "cached": trace.cached},
            )
        )

    def _span_stop(self, event: StopEvent) -> None:
        self._record(
            TraceRecord(
                kind="stop",
                run_id=event.run_id,
                item_id=event.item_id,
                name=event.reason.value,
                ok=False,
                error=_cut(event.detail),
                public_error=_public_detail(event),
                detail={
                    "scope": event.scope,
                    "steps": event.steps,
                    "cost_eur": str(event.cost_eur),
                },
            )
        )

    def outage(self, run_id: int, detail: str) -> None:
        """A database outage the worker waited out (finding 17#1: the durable record)."""
        self._record(
            TraceRecord(
                kind="outage",
                run_id=run_id,
                name="database_unavailable",
                ok=False,
                error=_cut(detail),
                public_error=_error_class(detail),
            )
        )

    def span_retrieval(self, trace: RetrievalTrace) -> None:
        """Hook for `mkc.rag.retriever.retrieve(tracers=...)` (MKC-50): latency and counts,
        never the query text. Outside a run (no scope) nothing is recorded here; `retrieve`
        logs its own line."""
        self._guarded("retrieval", self._span_retrieval, trace)

    def _span_retrieval(self, trace: RetrievalTrace) -> None:
        if trace.scope is None:
            return  # not part of a run: no trace to join
        self._record(
            TraceRecord(
                kind="retrieval",
                run_id=trace.scope.run_id,
                item_id=trace.scope.item_id,
                step=trace.scope.step,
                name="retrieve",
                ok=trace.error is None,
                error=_cut(trace.error),
                public_error=_error_class(trace.error),
                latency_ms=trace.latency_ms,
                detail={
                    "k": trace.k,
                    "query_chars": trace.query_chars,
                    "returned": trace.returned,
                    "keyword_hits": trace.keyword_hits,
                    "vector_hits": trace.vector_hits,
                },
            )
        )

    def flush(self) -> None:
        """Send what the sink still holds and forget the cached trace ids (the executor
        flushes after each run, so the cache stays small; a late event looks its id up
        again). Never raises."""
        with self._lock:
            self._trace_ids.clear()
        if self._sink is None:
            return
        try:
            self._sink.flush()
        except Exception as error:
            log.warning("trace sink flush failed: %s", _cut(f"{type(error).__name__}: {error}"))

    # --- one record, two sides ------------------------------------------------------------

    def _record(self, record: TraceRecord) -> None:
        trace_id = self._write(record)
        if self._sink is None:
            return
        if trace_id is None:  # without it Langfuse would open a trace of its own (19#2)
            log.warning("run %s: no trace id; %s kept in run_log only", record.run_id, record.kind)
            return
        try:
            self._sink.send(record, trace_id)
        except Exception as error:
            log.warning("run %s: %s not sent to the trace sink: %s", record.run_id, record.kind,
                        _cut(f"{type(error).__name__}: {error}"))  # fmt: skip

    def _write(self, record: TraceRecord) -> str | None:
        """Insert the `run_log` row; return the run's trace id (looked up once per run)."""
        with self._lock:
            trace_id = self._trace_ids.get(record.run_id)
        try:
            with self._sessions() as session:
                session.add(RunLog(**_row(record)))
                if trace_id is None:
                    trace_id = session.scalar(select(Run.trace_id).where(Run.id == record.run_id))
                session.commit()
        except Exception as error:
            log.warning("run %s: %s not written to run_log: %s", record.run_id, record.kind,
                        _cut(f"{type(error).__name__}: {error}"))  # fmt: skip
            return trace_id
        if trace_id is not None:
            with self._lock:
                self._trace_ids[record.run_id] = trace_id
        return trace_id


def _row(record: TraceRecord) -> dict[str, Any]:
    fields = asdict(record)
    fields["detail"] = record.detail or None
    del fields["public_error"]  # `error` holds the text; the public part is derived from it
    return fields


_HTTP = re.compile(r"\bHTTP (\d{3})\b")
_CLASS = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


def _error_class(text: str | None) -> str | None:
    """`<Class>: <text>` -> `<Class>`, plus ` (HTTP <status>)` when the text names one."""
    if text is None:
        return None
    head = text.split(":", 1)[0].strip()
    name = head if _CLASS.fullmatch(head) else "error"
    status = _HTTP.search(text)
    return f"{name[:MAX_NAME]} (HTTP {status.group(1)})" if status else name[:MAX_NAME]


def _public_detail(event: StopEvent) -> str | None:
    """A tool name for `tool_retries`; the error class for every other detail."""
    if event.detail is None:
        return None
    if event.reason is StopReason.TOOL_RETRIES:
        return event.detail[:MAX_NAME]
    return _error_class(event.detail)


def _cut(text: str | None) -> str | None:
    return None if text is None else text[:MAX_ERROR]


def _eur(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"))
