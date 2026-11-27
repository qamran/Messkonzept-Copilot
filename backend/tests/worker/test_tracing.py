"""MKC-19.4: the worker traces every run it processes (decision 59)."""

import threading
from collections import Counter
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from mkc.config import Settings
from mkc.models.client import ModelClient
from mkc.models.types import ModelConfigError
from mkc.observability.trace import Tracer
from mkc.worker.executor import Executor
from mkc.worker.main import build_executor
from tests.harness.conftest import make_run
from tests.harness.test_loop import SAVE, Tools, config
from tests.models.fakes import FakeChatModel, ai
from tests.observability.test_trace import FakeLangfuse, rows, trace_id
from tests.worker.test_executor import HookModel, read, settings
from tests.worker.test_outage import Outage


def traced_worker(
    engine: Engine, model: FakeChatModel, sink: FakeLangfuse, **overrides: Any
) -> Executor:
    tracer = Tracer(sessionmaker(bind=engine), sink)
    return Executor(
        settings(**overrides),
        sessions=sessionmaker(bind=engine),
        client_factory=lambda: ModelClient(
            config(), lambda p, n, t: model, mode="live", tracers=[tracer.span_model]
        ),
        registry=Tools().registry(tracers=[tracer.span_tool]),
        owner="w1",
        tracer=tracer,
    )


def test_a_run_gets_its_trace_id_and_every_event(engine: Engine) -> None:
    run_id, _ = make_run(engine, "queued", "queued")
    sink = FakeLangfuse()
    # item 1 saves; item 2 reads until its step limit (2) fails it
    model = HookModel(responses=[ai(tool_calls=[SAVE]), read(1), read(2)])
    with traced_worker(engine, model, sink, item_max_steps=2) as worker:
        assert worker.run_once() is True
    trace = trace_id(engine, run_id)
    assert trace is not None
    logged = Counter((r.kind, r.name) for r in rows(engine, run_id))
    assert logged[("stop", "step_limit")] == 1  # the executor passes the stop hook
    assert Counter(r.kind for r in rows(engine, run_id)) == Counter(
        {"model": 3, "tool": 3, "stop": 1}
    )
    assert {t for _, t in sink.sent} == {trace}
    assert sink.flushed >= 1  # flushed after the run


def test_a_setup_stop_reaches_the_tracer(engine: Engine) -> None:
    """Finding 18#3: `_stop_for_setup` passes the tracer's stop hook."""
    run_id, _ = make_run(engine, "queued")

    def broken() -> Any:
        raise ModelConfigError("no key")

    tracer = Tracer(sessionmaker(bind=engine), FakeLangfuse())
    worker = Executor(settings(worker_db_backoff_max_seconds=0.1),
                      sessions=sessionmaker(bind=engine), client_factory=broken,
                      registry=Tools().registry(), owner="w1", tracer=tracer)  # fmt: skip
    with worker:
        assert worker.run_once() is True
    assert [(r.kind, r.name, r.error) for r in rows(engine, run_id)] == [
        ("stop", "setup_error", "ModelConfigError")
    ]


def test_an_outage_the_worker_waits_out_leaves_a_row(engine: Engine, database_env: URL) -> None:
    """Finding 17#1: the run log is the durable record of an outage."""
    run_id, _ = make_run(engine, "queued")
    outage = Outage(database_env)
    restored = threading.Event()

    def cut_then_restore() -> None:
        outage.cut()

        def back() -> None:
            outage.restore()
            restored.set()

        threading.Timer(1.0, back).start()

    model = HookModel(responses=[read(1), read(2), read(2), ai(tool_calls=[SAVE])],
                      hooks={2: cut_then_restore})  # fmt: skip
    worker_engine = create_engine(database_env, pool_pre_ping=True)
    tracer = Tracer(sessionmaker(bind=worker_engine), FakeLangfuse())
    worker = Executor(settings(worker_db_backoff_max_seconds=0.2),
                      sessions=sessionmaker(bind=worker_engine),
                      client_factory=lambda: ModelClient(config(), lambda p, n, t: model,
                                                         mode="live"),
                      registry=Tools().registry(), owner="w1", tracer=tracer)  # fmt: skip
    try:
        with worker:
            assert worker.run_once() is True
            assert restored.is_set()
    finally:
        outage.restore()
        worker_engine.dispose()
    engine.dispose()
    outages = [r for r in rows(engine, run_id) if r.kind == "outage"]
    assert [(r.name, r.ok) for r in outages] == [("database_unavailable", False)]


def test_build_executor_wires_one_tracer(engine: Engine) -> None:
    """`main` builds one tracer: the executor holds it and the client and the registry
    report to it. No Langfuse keys: `run_log` only."""
    worker = build_executor(
        Settings(langfuse_public_key="", model_mode="live"), sessionmaker(bind=engine)
    )
    assert worker.tracer is not None
    model_hooks = worker._client_factory()._tracers  # type: ignore[attr-defined]
    assert model_hooks == [worker.tracer.span_model]
    assert worker._registry._tracers == (worker.tracer.span_tool,)  # type: ignore[attr-defined]
