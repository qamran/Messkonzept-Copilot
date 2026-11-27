"""MKC-19.3: a whole traced run: `run_log` matches the sink, and tracing never fails it."""

import logging
from collections import Counter
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mkc.harness.limits import Limits
from mkc.harness.loop import process_run
from mkc.models.client import ModelClient
from mkc.models.types import TransientModelError
from mkc.observability.trace import Tracer
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import READ, SAVE, Tools, call, config
from tests.models.fakes import FakeChatModel, ai, fake
from tests.observability.test_trace import BrokenSession, FakeLangfuse, rows, trace_id, tracer


def traced_run(engine: Engine, the_tracer: Tracer, model: FakeChatModel, limits: Limits) -> int:
    """One run through `process_run` with every hook on `the_tracer`; the first model call
    raises a transient error and is retried."""
    run_id, _ = make_run(engine, "queued")
    attempts = {"n": 0}

    def factory(provider: Any, name: str, timeout: float) -> FakeChatModel:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TimeoutError("first attempt times out")
        return model

    def classify(error: Exception) -> TransientModelError | None:
        return TransientModelError(str(error)) if isinstance(error, TimeoutError) else None

    client = ModelClient(config(), factory, mode="live", tracers=[the_tracer.span_model],
                         classify=classify)  # fmt: skip
    the_tracer.start_run(run_id)
    with Session(engine) as session:
        process_run(run_id, session=session, client=client,
                    registry=Tools().registry(tracers=[the_tracer.span_tool]), limits=limits,
                    tracers=[the_tracer.span_stop], sleep=lambda seconds: False)  # fmt: skip
    return run_id


def test_run_log_rows_match_span_counts(engine: Engine) -> None:
    sink = FakeLangfuse()
    bad = call("no_such_tool", "c9")
    model = fake(ai(tool_calls=[READ]), ai(tool_calls=[bad]), ai(tool_calls=[READ]))
    run_id = traced_run(engine, tracer(engine, sink), model, Limits(max_steps_run=3))
    logged = Counter(r.kind for r in rows(engine, run_id))
    sent = Counter(record.kind for record, _ in sink.sent)
    # 1 failed attempt + 3 calls; 3 tool calls (one refused); the run stop
    assert logged == sent == Counter({"model": 4, "tool": 3, "stop": 1})
    assert {t for _, t in sink.sent} == {trace_id(engine, run_id)}


def test_langfuse_down_run_continues(engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
    """Both sinks fail on every call: Langfuse raises, and every `run_log` write hits a
    database error. The run ends exactly as it would without tracing."""
    sink = FakeLangfuse(fail=True)
    broken = Tracer(lambda: BrokenSession(bind=engine), sink)
    model = fake(ai(tool_calls=[READ]), ai(tool_calls=[SAVE]))
    with caplog.at_level(logging.WARNING, logger="mkc.observability"):
        run_id = traced_run(engine, broken, model, Limits())
        broken.flush()
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])
    assert rows(engine, run_id) == [] and trace_id(engine, run_id) is None
    assert "langfuse down" in caplog.text and "database down" in caplog.text
