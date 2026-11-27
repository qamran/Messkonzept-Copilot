"""MKC-20.5: findings 1 to 3 of the PR #161 review (decision 60, point 9).

1. Only the error class (and an HTTP status) leaves for Langfuse; `run_log` keeps the text.
   A parsing error quotes the model reply, so its text must stay on the machine.
2. No trace id (start_run and the run_log lookup both failed): the sink is skipped.
3. A record that can't be built never leaves the tracer; the trace id cache is dropped on flush.
"""

from decimal import Decimal

from sqlalchemy import Engine

from mkc.harness.limits import StopEvent, StopReason
from mkc.harness.tools import ToolTrace
from mkc.models.client import TraceScope
from tests.harness.conftest import make_run
from tests.observability.test_trace import FakeLangfuse, model_trace, rows, tracer

PROMPT = "Extract the Messkonzept described by this item task: SECRET-PDF-TEXT"


def test_langfuse_gets_only_the_error_class(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    sink = FakeLangfuse()
    the_tracer = tracer(engine, sink)
    the_tracer.start_run(run_id)
    scope = TraceScope(run_id, item_id, 1)
    parse_error = f"ModelError: structured output did not parse: {PROMPT}"
    rate_limited = "TransientModelError: HTTP 429 (RateLimitError)"
    the_tracer.span_model(model_trace(scope, usage=None, error=parse_error))
    the_tracer.span_model(model_trace(scope, usage=None, error=rate_limited))
    (parsing, _), (limited, _) = sink.sent
    assert parsing.public_error == "ModelError"
    assert limited.public_error == "TransientModelError (HTTP 429)"
    assert PROMPT in (rows(engine, run_id)[0].error or "")  # the text stays in run_log


def test_stop_details_leave_as_class_or_cut_tool_name(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    sink = FakeLangfuse()
    the_tracer = tracer(engine, sink)
    the_tracer.start_run(run_id)
    zero = Decimal(0)
    the_tracer.span_stop(StopEvent("item", run_id, item_id, StopReason.TOOL_RETRIES,
                                   "t" * 300, 4, zero))  # fmt: skip
    outage = f"TransientModelError: HTTP 503 ({PROMPT})"
    the_tracer.span_stop(StopEvent("run", run_id, item_id, StopReason.MODEL_UNAVAILABLE,
                                   outage, 9, zero))  # fmt: skip
    (retries, _), (unavailable, _) = sink.sent
    assert retries.public_error == "t" * 100
    assert unavailable.public_error == "TransientModelError (HTTP 503)"


def test_no_trace_id_skips_the_sink(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    sink = FakeLangfuse()
    tracer(engine, sink).span_model(model_trace(TraceScope(run_id, item_id, 1)))  # no start_run
    assert sink.sent == []
    assert len(rows(engine, run_id)) == 1  # run_log still records


def test_span_record_errors_stay_inside_the_tracer(engine: Engine) -> None:
    """The hooks run inside the loop's model and tool calls: a bad trace must not fail them."""
    run_id, (item_id,) = make_run(engine, "running")
    nameless = ToolTrace(None, "item", True, None, False, 1, run_id=run_id, item_id=item_id)  # type: ignore[arg-type]
    tracer(engine).span_tool(nameless)  # `None[:100]` raises while the record is built
    assert rows(engine, run_id) == []


def test_trace_id_cache_is_dropped_after_flush(engine: Engine) -> None:
    run_id, _ = make_run(engine, "running")
    the_tracer = tracer(engine, FakeLangfuse())
    the_tracer.start_run(run_id)
    assert the_tracer._trace_ids
    the_tracer.flush()
    assert the_tracer._trace_ids == {}
