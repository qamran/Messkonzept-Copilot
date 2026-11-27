"""MKC-50.1 and 50.3 (development agent): the retriever's own rules and how a retrieval
reaches the run's trace (coordinator decision on the test agent's question 1, decision 80).

- With a run scope, `Tracer.span_retrieval` writes one `run_log` row (kind `retrieval`) and
  one sink record in the run's trace, with the latency and counts only.
- Outside a run, no row and no sink call; `retrieve` writes one log line with the latency.
- The keyword side ORs the query's terms (decision 79), so a question in words still finds
  the chunks that share any term.
"""

import logging
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import RunLog
from mkc.models.client import TraceScope
from mkc.observability.trace import Tracer
from tests.harness.conftest import engine, make_run
from tests.observability.test_langfuse import ATTR, TRACE, attrs, exported, spans
from tests.observability.test_trace import FakeLangfuse
from tests.rag.test_retriever import ScriptedEmbedder, corpus, dim, session

__all__ = ["corpus", "dim", "engine", "exported", "session"]


def _retrieve(session: Session, query: str, k: int, embedder: Any, **kwargs: Any) -> list[Any]:
    from mkc.rag.retriever import retrieve

    return retrieve(query, k, session=session, embedder=embedder, **kwargs)


def _log_rows(engine: Engine) -> list[RunLog]:
    with Session(engine) as s:
        found = list(s.scalars(select(RunLog).order_by(RunLog.id)))
        s.expunge_all()
        return found


# --- the retriever's own rules -----------------------------------------------------------


def test_the_keyword_side_ors_the_query_terms(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    """No chunk holds both words; each word is in one chunk. AND would find nothing."""
    seen: list[Any] = []
    found = _retrieve(session, "Wärmepumpe Zweirichtungszähler", 2, ScriptedEmbedder(dim),
                      tracers=[seen.append])  # fmt: skip
    assert seen[0].keyword_hits == 2
    assert {c.source_ref for c in found} == {"§ 2 Abs. 3", "§ 3 Abs. 2"}


def test_a_chunk_with_more_query_terms_ranks_first_on_the_keyword_side(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    """`§ 14a Abs. 2` has "Steuerung" twice and "erfolgt"; the decision has "Steuerung" once."""
    found = _retrieve(session, "Steuerung erfolgt", 1, ScriptedEmbedder(dim))
    assert found[0].source_ref == "§ 14a Abs. 2"


def test_refused_arguments_are_not_traced(session: Session, dim: int) -> None:
    """A wrong `k` or a blank query is the caller's bug: nothing ran, so nothing is traced."""
    seen: list[Any] = []
    for query, k in (("§ 14a", 0), (" ", 3)):
        with pytest.raises(ValueError):
            _retrieve(session, query, k, ScriptedEmbedder(dim), tracers=[seen.append])
    assert seen == []


def test_each_call_writes_one_log_line_without_the_query(
    corpus: dict[str, int], session: Session, dim: int, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="mkc.rag.retriever"):
        _retrieve(session, "Wärmepumpe", 3, ScriptedEmbedder(dim))
    (record,) = [r for r in caplog.records if r.name == "mkc.rag.retriever"]
    line = record.getMessage()
    assert "latency_ms=" in line and "returned=3" in line and "error=None" in line
    assert "rmepumpe" not in line


def test_a_failed_call_logs_the_error_class_only(
    corpus: dict[str, int], session: Session, dim: int, caplog: pytest.LogCaptureFixture
) -> None:
    embedder = ScriptedEmbedder(dim, fail=RuntimeError("provider echoed Wärmepumpe"))
    with caplog.at_level(logging.INFO, logger="mkc.rag.retriever"), pytest.raises(RuntimeError):
        _retrieve(session, "Wärmepumpe", 3, embedder)
    (record,) = [r for r in caplog.records if r.name == "mkc.rag.retriever"]
    assert "error=RuntimeError" in record.getMessage()
    assert "rmepumpe" not in record.getMessage()


# --- the bridge to run_log and Langfuse ---------------------------------------------------


def test_a_retrieval_in_a_run_is_one_run_log_row_and_one_sink_record(
    engine: Engine, corpus: dict[str, int], session: Session, dim: int
) -> None:
    run_id, (item_id,) = make_run(engine, "running")
    sink = FakeLangfuse()
    tracer = Tracer(sessionmaker(bind=engine), sink)
    trace_id = tracer.start_run(run_id)
    seen: list[Any] = []
    _retrieve(session, "§ 14a", 3, ScriptedEmbedder(dim), tracers=[tracer.span_retrieval,
              seen.append], scope=TraceScope(run_id, item_id, 2))  # fmt: skip
    (row,) = _log_rows(engine)
    assert (row.kind, row.name, row.ok, row.run_id, row.item_id, row.step) == (
        "retrieval", "retrieve", True, run_id, item_id, 2)  # fmt: skip
    assert row.latency_ms == seen[0].latency_ms
    counts = {"k": 3, "query_chars": 5, "returned": 3, "keyword_hits": 3, "vector_hits": 10}
    assert row.detail == counts
    ((record, sent_to),) = sink.sent
    assert sent_to == trace_id
    assert (record.kind, record.latency_ms, record.detail) == ("retrieval", row.latency_ms, counts)
    assert "14a" not in repr(record) and "14a" not in repr(row.__dict__)


def test_a_retrieval_outside_a_run_writes_no_row_and_calls_no_sink(
    engine: Engine, corpus: dict[str, int], session: Session, dim: int
) -> None:
    sink = FakeLangfuse()
    tracer = Tracer(sessionmaker(bind=engine), sink)
    seen: list[Any] = []
    _retrieve(session, "§ 14a", 3, ScriptedEmbedder(dim), tracers=[tracer.span_retrieval,
              seen.append])  # fmt: skip
    assert len(seen) == 1, "the hooks still get the trace"
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(RunLog)) == 0
    assert sink.sent == []


def test_a_failed_retrieval_sends_the_error_class_only(engine: Engine) -> None:
    from mkc.rag.retriever import RetrievalTrace

    run_id, _ = make_run(engine, "running")
    sink = FakeLangfuse()
    tracer = Tracer(sessionmaker(bind=engine), sink)
    tracer.start_run(run_id)
    tracer.span_retrieval(RetrievalTrace(latency_ms=12, k=3, query_chars=5, returned=0,
                                         keyword_hits=0, vector_hits=0,
                                         error="RuntimeError: provider echoed § 14a",
                                         scope=TraceScope(run_id)))  # fmt: skip
    ((record, _),) = sink.sent
    assert (record.ok, record.public_error) == (False, "RuntimeError")
    (row,) = _log_rows(engine)
    assert (row.kind, row.ok, row.latency_ms) == ("retrieval", False, 12)


def test_a_retrieval_record_is_a_retriever_observation(exported: Any) -> None:
    from mkc.observability.trace import TraceRecord

    sink, exporter = exported
    counts = {"k": 3, "query_chars": 5, "returned": 3, "keyword_hits": 3, "vector_hits": 10}
    sink.send(TraceRecord(kind="retrieval", run_id=7, item_id=3, step=2, name="retrieve",
                          ok=True, latency_ms=42, detail=counts), TRACE)  # fmt: skip
    (span,) = spans(sink, exporter)
    found = attrs(span)
    assert format(span.context.trace_id, "032x") == TRACE
    assert found[ATTR + "type"] == "retriever"
    assert span.name == "retrieve"
    assert found[ATTR + "metadata.latency_ms"] == "42"
    assert found[ATTR + "metadata.keyword_hits"] == "3"
    assert (span.end_time or 0) - (span.start_time or 0) >= 42 * 1_000_000


def test_the_demo_expects_a_retriever_for_a_retrieval_row() -> None:
    """The live demo compares `run_log` kinds with Langfuse's observation types."""
    from collections import Counter

    from mkc.observability.demo import expected_types

    assert expected_types(["retrieval"]) == Counter({"RETRIEVER": 1})


class FailingSession(Session):
    """A database error whose text quotes the statement's parameters, as SQLAlchemy's do."""

    def scalars(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        from sqlalchemy.exc import OperationalError

        raise OperationalError(str(statement), params, Exception("server closed the connection"))


def test_a_database_error_never_puts_the_query_into_the_trace(
    engine: Engine, corpus_engine: Engine, dim: int, caplog: pytest.LogCaptureFixture
) -> None:
    """`str()` of a SQLAlchemy error ends with `[parameters: {'query': …}]`: the trace keeps
    the error class (and the SQLSTATE when there is one), never the message."""
    from sqlalchemy.exc import OperationalError

    run_id, _ = make_run(engine, "running")
    tracer = Tracer(sessionmaker(bind=engine), FakeLangfuse())
    tracer.start_run(run_id)
    seen: list[Any] = []
    with FailingSession(corpus_engine) as failing, pytest.raises(OperationalError) as raised:
        hooks = [tracer.span_retrieval, seen.append]
        _retrieve(failing, "Wärmepumpe Musterstraße", 3, ScriptedEmbedder(dim), tracers=hooks,
                  scope=TraceScope(run_id))  # fmt: skip
    assert "Musterstraße" in str(raised.value), "the caller still gets the full error"
    (trace,) = seen
    assert trace.error is not None and trace.error.startswith("OperationalError")
    assert "Musterstra" not in trace.error and "rmepumpe" not in trace.error
    (row,) = _log_rows(engine)
    assert row.error is not None and "Musterstra" not in row.error
    assert "Musterstra" not in caplog.text
