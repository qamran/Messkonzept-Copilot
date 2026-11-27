"""MKC-50 acceptance tests for `mkc.rag.retriever.retrieve` on the test database.

The corpus is inserted row by row with hand-made unit vectors, so the vector side's order is
known whatever distance the retriever uses (cosine, L2 and inner product agree on unit
vectors). The query embedder always returns `e0`; each chunk's cosine to it is set below.
"""

import math
import time
from collections.abc import Iterator, Sequence
from dataclasses import fields
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mkc.models.client import TraceScope

# (source_ref, text, cosine to the query vector). Vector order: F1 … F6, M, B, T2, T1.
LAW = [
    ("§ 1 Abs. 1", "§ 1 Zweck\n(1) Dieses Gesetz regelt den Messstellenbetrieb.", 0.95),
    ("§ 1 Abs. 2", "§ 1 Zweck\n(2) Es gilt für alle Messstellenbetreiber.", 0.90),
    ("§ 3 Abs. 1", "§ 3 Zähler\n(1) Ein Zähler misst den Bezug.", 0.85),
    ("§ 3 Abs. 2", "§ 3 Zähler\n(2) Ein Zweirichtungszähler misst auch Einspeisung.", 0.80),
    ("§ 4 Abs. 1", "§ 4 Gateway\n(1) Das Gateway sendet Messwerte.", 0.75),
    ("§ 4 Abs. 2", "§ 4 Gateway\n(2) Der Betreiber prüft das Gateway jährlich.", 0.70),
    ("§ 2 Abs. 3", "§ 2 Begriffe\n(3) Steuerbar ist eine Wärmepumpe nach § 14a.", 0.50),
    ("§ 14a Abs. 2", "§ 14a Netzorientierte Steuerung\n(2) Die Steuerung erfolgt so.", -0.90),
    ("§ 14a Abs. 1", "§ 14a Netzorientierte Steuerung\n(1) Netzbetreiber steuern.", -1.00),
]
DECISION = [
    ("Abschnitt 3", "3 Festlegung\nDie Festlegung BK6-22-300 regelt die Steuerung.", -0.80),
]
VECTOR_ORDER = [ref for ref, _, _ in sorted(LAW + DECISION, key=lambda row: -row[2])]


def _vector(cosine: float, axis: int, dim: int) -> list[float]:
    """A unit vector with the given cosine to `e0`, turned towards its own axis."""
    vector = [0.0] * dim
    vector[0] = cosine
    vector[axis] = math.sqrt(max(0.0, 1.0 - cosine * cosine))
    return vector


class ScriptedEmbedder:
    """Every query embeds to `e0`; passages are never embedded by the retriever."""

    def __init__(self, dim: int, delay: float = 0.0, fail: Exception | None = None) -> None:
        self.dim = dim
        self.model = "scripted"
        self.delay = delay
        self.fail = fail
        self.queries: list[str] = []

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        if self.delay:
            time.sleep(self.delay)
        if self.fail is not None:
            raise self.fail
        return _vector(1.0, 1, self.dim)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError("the retriever embeds the query with embed_query only")


def _insert(session: Session, source_id: str, source_type: str, rows: list[Any], axis: int,
            dim: int) -> dict[str, int]:  # fmt: skip
    from mkc.db.models import Chunk as ChunkRow
    from mkc.db.models import CorpusDocument

    document = CorpusDocument(
        source_id=source_id,
        title=f"{source_id} (synthetisch)",
        source_type=source_type,
        url=f"https://example.org/{source_id}",
        version="2026",
        licence="official",
    )
    session.add(document)
    session.flush()
    ids: dict[str, int] = {}
    for ordinal, (ref, body, cosine) in enumerate(rows):
        row = ChunkRow(
            document_id=document.id,
            ordinal=ordinal,
            source_ref=ref,
            text=body,
            embedding=_vector(cosine, axis + ordinal, dim),
        )
        session.add(row)
        session.flush()
        ids[ref] = row.id
    return ids


@pytest.fixture
def dim() -> int:
    from mkc.rag.embeddings import EMBEDDING

    return EMBEDDING.dim


@pytest.fixture
def corpus(corpus_engine: Engine, dim: int) -> dict[str, int]:
    """The ten chunks above; returns chunk id by source_ref."""
    with Session(corpus_engine) as session, session.begin():
        ids = _insert(session, "musterg", "law", LAW, 2, dim)
        ids |= _insert(session, "bk6-muster", "bnetza_decision", DECISION, 20, dim)
    return ids


@pytest.fixture
def session(corpus_engine: Engine) -> Iterator[Session]:
    with Session(corpus_engine) as s:
        yield s


def _retrieve(session: Session, query: str, k: int, embedder: Any, **kwargs: Any) -> list[Any]:
    from mkc.rag.retriever import retrieve

    return retrieve(query, k, session=session, embedder=embedder, **kwargs)


# --- the keyword side finds paragraph references --------------------------------------------


def test_paragraph_reference_found_by_keyword(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    """The vector side ranks both § 14a chunks last; the keyword side still brings them in."""
    assert VECTOR_ORDER[-2:] == ["§ 14a Abs. 2", "§ 14a Abs. 1"]
    assert not {"§ 14a Abs. 1", "§ 14a Abs. 2"} & set(VECTOR_ORDER[:3])
    found = _retrieve(session, "§ 14a", 3, ScriptedEmbedder(dim))
    refs = [c.source_ref for c in found]
    assert {"§ 14a Abs. 1", "§ 14a Abs. 2"} <= set(refs), refs
    assert set(refs) == {"§ 14a Abs. 1", "§ 14a Abs. 2", "§ 2 Abs. 3"}, "the 3 keyword hits"


def test_a_decision_number_is_found_by_keyword(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    found = _retrieve(session, "BK6-22-300", 3, ScriptedEmbedder(dim))
    assert found[0].source_ref == "Abschnitt 3"
    assert found[0].chunk_id == corpus["Abschnitt 3"]


def test_a_query_without_keyword_hits_uses_the_vector_side(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    found = _retrieve(session, "Photovoltaik Batteriespeicher", 3, ScriptedEmbedder(dim))
    assert [c.source_ref for c in found] == VECTOR_ORDER[:3]


# --- the result -----------------------------------------------------------------------------


def test_results_are_ranked_unique_and_at_most_k(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    from mkc.rag.retriever import RetrievedChunk

    found = _retrieve(session, "§ 14a", 5, ScriptedEmbedder(dim))
    assert len(found) == 5
    assert all(isinstance(c, RetrievedChunk) for c in found)
    scores = [c.score for c in found]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)
    assert len({c.chunk_id for c in found}) == 5
    by_ref = {ref: body for ref, body, _ in LAW + DECISION}
    for chunk in found:
        assert corpus[chunk.source_ref] == chunk.chunk_id
        assert chunk.text == by_ref[chunk.source_ref], "the stored text, unchanged"


def test_the_score_is_the_rrf_score(corpus: dict[str, int], session: Session, dim: int) -> None:
    """BK6-22-300 has one keyword hit (rank 1) that is 8th on the vector side."""
    found = _retrieve(session, "BK6-22-300", 1, ScriptedEmbedder(dim))
    assert found[0].score == pytest.approx(1 / 61 + 1 / 68)


def test_an_empty_corpus_returns_nothing(corpus_engine: Engine, session: Session, dim: int) -> None:
    assert _retrieve(session, "§ 14a", 5, ScriptedEmbedder(dim)) == []


def test_the_query_is_embedded_once_as_given(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    """The model's query instruction lives in the embedder (`embed_query`), not here."""
    embedder = ScriptedEmbedder(dim)
    _retrieve(session, "Wann gilt § 14a?", 3, embedder)
    assert embedder.queries == ["Wann gilt § 14a?"]


def test_search_operators_in_the_query_are_plain_text(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    found = _retrieve(session, "Wärmepumpe & (§ 14a) | !:' <-> *", 3, ScriptedEmbedder(dim))
    assert len(found) == 3


@pytest.mark.parametrize("k", [0, -1])
def test_k_below_one_is_refused(session: Session, dim: int, k: int) -> None:
    embedder = ScriptedEmbedder(dim)
    with pytest.raises(ValueError):
        _retrieve(session, "§ 14a", k, embedder)
    assert embedder.queries == []


def test_k_above_the_cap_is_refused(session: Session, dim: int) -> None:
    from mkc.rag.retriever import CANDIDATES, MAX_K

    assert 10 <= MAX_K <= CANDIDATES, "each side looks at no fewer candidates than k"
    _retrieve(session, "§ 14a", MAX_K, ScriptedEmbedder(dim))  # the cap itself is allowed
    with pytest.raises(ValueError):
        _retrieve(session, "§ 14a", MAX_K + 1, ScriptedEmbedder(dim))


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_a_blank_query_is_refused(session: Session, dim: int, query: str) -> None:
    embedder = ScriptedEmbedder(dim)
    with pytest.raises(ValueError):
        _retrieve(session, query, 3, embedder)
    assert embedder.queries == []


# --- latency per query in the trace --------------------------------------------------------


def test_latency_per_query_logged_in_the_trace(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    """One `RetrievalTrace` per call, with the latency of the whole query (embedding
    included) and its sizes; never the query text."""
    from mkc.rag.retriever import RetrievalTrace

    seen: list[Any] = []
    scope = TraceScope(run_id=7, item_id=3, step=2)
    found = _retrieve(session, "§ 14a", 3, ScriptedEmbedder(dim, delay=0.05),
                      tracers=[seen.append], scope=scope)  # fmt: skip
    (trace,) = seen
    assert isinstance(trace, RetrievalTrace)
    assert isinstance(trace.latency_ms, int)
    assert trace.latency_ms >= 50, "the embed call is inside the measured time"
    assert (trace.k, trace.query_chars, trace.returned) == (3, len("§ 14a"), len(found))
    assert (trace.keyword_hits, trace.vector_hits) == (3, 10)
    assert trace.error is None
    assert trace.scope == scope
    names = {f.name for f in fields(trace)}
    assert {"latency_ms", "k", "query_chars", "returned", "keyword_hits", "vector_hits",
            "error", "scope"} <= names  # fmt: skip
    assert not {"query", "text"} & names
    for name in names:
        value = getattr(trace, name)
        assert not (isinstance(value, str) and "14a" in value), f"{name} holds the query"


def test_a_failed_query_is_traced_and_raised(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    seen: list[Any] = []
    embedder = ScriptedEmbedder(dim, fail=RuntimeError("provider down"))
    with pytest.raises(RuntimeError, match="provider down"):
        _retrieve(session, "§ 14a", 3, embedder, tracers=[seen.append])
    (trace,) = seen
    assert trace.error is not None and trace.error.startswith("RuntimeError")
    assert trace.returned == 0
    assert trace.scope is None


def test_a_failing_trace_hook_does_not_break_retrieval(
    corpus: dict[str, int], session: Session, dim: int
) -> None:
    def broken(trace: Any) -> None:
        raise RuntimeError("tracer down")

    seen: list[Any] = []
    found = _retrieve(session, "§ 14a", 3, ScriptedEmbedder(dim), tracers=[broken, seen.append])
    assert len(found) == 3
    assert len(seen) == 1, "the next hook still gets the trace"
