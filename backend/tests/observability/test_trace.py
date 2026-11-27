"""MKC-19.3: the `Tracer` writes each event to `run_log` and a sink (decision 59)."""

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Run, RunLog
from mkc.harness.limits import StopEvent, StopReason
from mkc.harness.tools import ToolTrace
from mkc.models.client import CallTrace, TraceScope
from mkc.models.types import Usage
from mkc.observability.trace import Tracer, TraceRecord
from tests.harness.conftest import make_run

USAGE = Usage(input_tokens=100, output_tokens=20, cost_eur=0.0003)


class FakeLangfuse:
    """A fake Langfuse sink: records what it is sent, or fails on every call."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[TraceRecord, str | None]] = []
        self.flushed = 0

    def send(self, record: TraceRecord, trace_id: str | None) -> None:
        if self.fail:
            raise ConnectionError("langfuse down")
        self.sent.append((record, trace_id))

    def flush(self) -> None:
        if self.fail:
            raise ConnectionError("langfuse down")
        self.flushed += 1


class BrokenSession(Session):
    """A session whose database is gone: every statement and commit fails."""

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise OperationalError("statement", {}, Exception("database down"))

    def commit(self) -> None:
        raise OperationalError("commit", {}, Exception("database down"))


def tracer(engine: Engine, sink: FakeLangfuse | None = None) -> Tracer:
    return Tracer(sessionmaker(bind=engine), sink)


def rows(engine: Engine, run_id: int) -> list[RunLog]:
    with Session(engine) as session:
        found = session.scalars(select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.id))
        result = list(found)
        session.expunge_all()
        return result


def trace_id(engine: Engine, run_id: int) -> str | None:
    with Session(engine) as session:
        return session.get_one(Run, run_id).trace_id


def model_trace(scope: TraceScope | None, **kw: Any) -> CallTrace:
    fields: dict[str, Any] = {"role": "extract_vision", "method": "chat_with_tools",
                              "mode": "live", "model_id": "openrouter:a/cheap",
                              "latency_ms": 840, "usage": USAGE, "error": None}  # fmt: skip
    return CallTrace(**(fields | kw), scope=scope)


# --- the records -------------------------------------------------------------------------


def test_start_run_sets_the_trace_id_once(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued")
    first = tracer(engine).start_run(run_id)
    assert first is not None and re.fullmatch(r"[0-9a-f]{32}", first)
    assert tracer(engine).start_run(run_id) == first  # a second worker reuses it
    assert trace_id(engine, run_id) == first


def test_spans_have_the_required_fields(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    sink = FakeLangfuse()
    the_tracer = tracer(engine, sink)
    trace = the_tracer.start_run(run_id)
    the_tracer.span_model(model_trace(TraceScope(run_id, item_id, 1)))
    the_tracer.span_tool(ToolTrace("extract_text", "item", True, None, False, 12,
                                   run_id=run_id, item_id=item_id, step=1))  # fmt: skip
    the_tracer.span_stop(StopEvent("item", run_id, item_id, StopReason.STEP_LIMIT, None, 12,
                                   Decimal("0.0036")))  # fmt: skip
    (model, t1), (tool, t2), (stop, t3) = sink.sent
    assert t1 == t2 == t3 == trace
    assert (model.kind, model.run_id, model.item_id, model.step) == ("model", run_id, item_id, 1)
    assert (model.name, model.ok, model.error, model.mode) == ("openrouter:a/cheap", True, None,
                                                               "live")  # fmt: skip
    assert (model.input_tokens, model.output_tokens, model.latency_ms) == (100, 20, 840)
    assert model.cost_eur == Decimal("0.000300")
    assert model.detail == {"role": "extract_vision", "method": "chat_with_tools"}
    assert (tool.kind, tool.name, tool.ok, tool.step, tool.latency_ms) == ("tool",
                                                                           "extract_text",
                                                                           True, 1, 12)  # fmt: skip
    assert (stop.kind, stop.name, stop.ok, stop.item_id) == ("stop", "step_limit", False, item_id)
    assert stop.detail == {"scope": "item", "steps": 12, "cost_eur": "0.0036"}
    logged = rows(engine, run_id)
    assert [(r.kind, r.name, r.ok, r.step) for r in logged] == [
        ("model", "openrouter:a/cheap", True, 1),
        ("tool", "extract_text", True, 1),
        ("stop", "step_limit", False, None),
    ]
    assert (logged[0].input_tokens, logged[0].cost_eur, logged[0].mode) == (100,
                                                                            Decimal("0.000300"),
                                                                            "live")  # fmt: skip


def test_failed_call_is_recorded_with_its_error_and_no_cost(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    the_tracer = tracer(engine)
    the_tracer.span_model(model_trace(TraceScope(run_id, item_id, 2), usage=None,
                                      error="TimeoutError: slow"))  # fmt: skip
    (row,) = rows(engine, run_id)
    assert (row.ok, row.error, row.input_tokens, row.cost_eur) == (False, "TimeoutError: slow",
                                                                   None, None)  # fmt: skip


def test_late_trace_lands_on_its_own_item_and_step(engine: Engine) -> None:
    """A call abandoned at the deadline reports after the loop moved on; its ids travel
    with it, so its cost lands where it was spent."""
    run_id, (first, second) = make_run(engine, "failed", "running")
    the_tracer = tracer(engine)
    the_tracer.span_model(model_trace(TraceScope(run_id, second, 1)))
    the_tracer.span_model(model_trace(TraceScope(run_id, first, 4)))  # the late one
    assert [(r.item_id, r.step) for r in rows(engine, run_id)] == [(second, 1), (first, 4)]


def test_name_and_error_are_cut_before_they_leave(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    sink = FakeLangfuse()
    the_tracer = tracer(engine, sink)
    the_tracer.span_tool(ToolTrace("x" * 500, "item", False, "unknown_tool", True, 1,
                                   run_id=run_id, item_id=item_id, step=1))  # fmt: skip
    the_tracer.span_model(model_trace(TraceScope(run_id, item_id, 1), usage=None,
                                      error="E" * 2000))  # fmt: skip
    (tool, _), (model, _) = sink.sent
    assert len(tool.name) == 100 and tool.detail["refused"] is True
    assert model.error is not None and len(model.error) == 500


def test_untraced_calls_are_skipped(engine: Engine) -> None:
    """A call outside a run (no scope, no run id) has no trace to join."""
    sink = FakeLangfuse()
    the_tracer = tracer(engine, sink)
    the_tracer.span_model(model_trace(None))
    the_tracer.span_tool(ToolTrace("extract_text", "item", True, None, False, 1))
    assert sink.sent == []


def test_outage_is_recorded(engine: Engine) -> None:
    run_id, _ = make_run(engine, "running")
    tracer(engine).outage(run_id, "OperationalError")
    (row,) = rows(engine, run_id)
    assert (row.kind, row.name, row.ok, row.error) == ("outage", "database_unavailable", False,
                                                       "OperationalError")  # fmt: skip
