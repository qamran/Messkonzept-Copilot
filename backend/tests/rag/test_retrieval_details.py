"""MKC-50 mutation pass (test agent): details of `retrieve` and its trace that no earlier
test could fail for. Each test names the survivor it kills in the lane file."""

import logging
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.models.client import TraceScope
from mkc.observability.trace import Tracer
from tests.harness.conftest import engine
from tests.observability.test_langfuse import ATTR, TRACE, attrs, exported, spans
from tests.observability.test_trace import FakeLangfuse
from tests.rag.test_retriever import ScriptedEmbedder, _vector, corpus, dim, session

__all__ = ["corpus", "dim", "engine", "exported", "session"]


def _retrieve(session: Session, query: str, k: int, embedder: Any, **kwargs: Any) -> list[Any]:
    from mkc.rag.retriever import retrieve

    return retrieve(query, k, session=session, embedder=embedder, **kwargs)


def test_the_vector_side_ranks_by_cosine_not_by_length(corpus_engine: Engine, dim: int) -> None:
    """ "Lang" points exactly along the query but is ten times as long: first by cosine, last
    by L2 distance (9 against at most 1.42 for the unit vectors)."""
    from mkc.db.models import Chunk as ChunkRow
    from mkc.db.models import CorpusDocument

    long_vector = [10 * x for x in _vector(1.0, 2, dim)]
    rows = [("Abschnitt 1", "Kurz eins", _vector(0.9, 3, dim)),
            ("Abschnitt 2", "Kurz zwei", _vector(0.8, 4, dim)),
            ("Abschnitt 3", "Lang", long_vector)]  # fmt: skip
    with Session(corpus_engine) as s, s.begin():
        document = CorpusDocument(source_id="vec", title="Vektoren (synthetisch)",
                                  source_type="operator_text", url="https://example.org/vec",
                                  version="2026", licence="restricted")  # fmt: skip
        s.add(document)
        s.flush()
        for ordinal, (ref, body, vector) in enumerate(rows):
            s.add(ChunkRow(document_id=document.id, ordinal=ordinal, source_ref=ref, text=body,
                           embedding=vector))  # fmt: skip
    with Session(corpus_engine) as s:
        found = _retrieve(s, "Photovoltaik", 3, ScriptedEmbedder(dim))
    assert [c.source_ref for c in found] == ["Abschnitt 3", "Abschnitt 1", "Abschnitt 2"]


class WrongDimEmbedder(ScriptedEmbedder):
    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [1.0, 0.0, 0.0]


def test_a_database_error_keeps_its_sqlstate(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    """A vector of the wrong dimension makes Postgres refuse the query: the trace keeps the
    error class and the SQLSTATE, never the message."""
    seen: list[Any] = []
    with pytest.raises(Exception):  # noqa: B017 - the driver's error class is not the point
        _retrieve(session, "§ 14a", 3, WrongDimEmbedder(dim), tracers=[seen.append])
    (trace,) = seen
    name, rest = trace.error.split(": ", 1)
    assert name and rest.startswith("SQLSTATE ")
    assert len(rest.removeprefix("SQLSTATE ")) == 5, trace.error


def test_query_chars_counts_the_query_as_given(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    seen: list[Any] = []
    _retrieve(session, "  § 14a  ", 3, ScriptedEmbedder(dim), tracers=[seen.append])
    assert seen[0].query_chars == 9


def test_the_log_line_ends_with_the_error_class_alone(
    corpus: dict[str, int], session: Session, dim: int, caplog: pytest.LogCaptureFixture
) -> None:
    embedder = ScriptedEmbedder(dim, fail=RuntimeError("down"))
    with caplog.at_level(logging.INFO, logger="mkc.rag.retriever"), pytest.raises(RuntimeError):
        _retrieve(session, "§ 14a", 3, embedder)
    (record,) = [r for r in caplog.records if r.name == "mkc.rag.retriever"]
    assert record.getMessage().endswith(" error=RuntimeError")


def test_span_retrieval_never_raises(engine: Engine) -> None:
    """A trace it cannot read is logged and dropped, like the other `Tracer` hooks."""
    tracer = Tracer(sessionmaker(bind=engine), FakeLangfuse())
    tracer.span_retrieval(SimpleNamespace(scope=TraceScope(run_id=1)))  # type: ignore[arg-type]


def test_a_retrieval_outside_a_run_is_skipped_quietly(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    from mkc.rag.retriever import RetrievalTrace

    tracer = Tracer(sessionmaker(bind=engine), FakeLangfuse())
    with caplog.at_level(logging.WARNING, logger="mkc.observability.trace"):
        trace = RetrievalTrace(latency_ms=1, k=3, query_chars=5, returned=3, keyword_hits=1,
                               vector_hits=3, error=None)  # fmt: skip
        tracer.span_retrieval(trace)
    assert caplog.records == []


def test_a_failed_retrieval_shows_only_its_error_class_in_langfuse(exported: Any) -> None:
    from mkc.observability.trace import TraceRecord

    sink, exporter = exported
    sink.send(TraceRecord(kind="retrieval", run_id=7, name="retrieve", ok=False, latency_ms=5,
                          error="RuntimeError: provider echoed § 14a",
                          public_error="RuntimeError"), TRACE)  # fmt: skip
    (span,) = spans(sink, exporter)
    found = attrs(span)
    assert found[ATTR + "level"] == "ERROR"
    assert found[ATTR + "status_message"] == "RuntimeError"
