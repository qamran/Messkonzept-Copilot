"""The hybrid retriever (MKC-50, feature 71, decisions 79 and 80).

`retrieve(query, k)` asks two sides and fuses their rankings with reciprocal rank fusion:

- **Keyword:** Postgres full-text search on `chunk.tsv` with the `german` configuration (the
  one `chunk.tsv` is built with, so "Wärmepumpen" finds "Wärmepumpe"). The query is plain
  text: `plainto_tsquery` reads no operators, and its terms are ORed, so a question in words
  finds every chunk that shares a term; `ts_rank` puts the chunks with more terms first. A
  paragraph reference like "§ 14a" or a decision number like "BK6-22-300" is a term, which
  is what the vector side is weak at.
- **Vector:** the query's embedding (`embed_query`, with the model's query instruction)
  against `chunk.embedding` by cosine distance.

Each side looks at up to `CANDIDATES` chunks; ties go to the lower chunk id everywhere, so
the result is deterministic. A chunk's text is untrusted data: a prompt takes it only
through `RetrievedChunk.as_prompt_data()`, never `text` directly (MKC-51).

Tracing: one `RetrievalTrace` per call (latency of the whole call, embedding included, and
counts; never the query text) to each hook, and one log line. `Tracer.span_retrieval` is the
hook that writes it to `run_log` and Langfuse when the call has a run scope.
"""

import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session
from sqlalchemy.types import BigInteger

from mkc.models.client import TraceScope
from mkc.rag.embeddings import QueryEmbedder

log = logging.getLogger(__name__)

RRF_K = 60
"""The constant of reciprocal rank fusion (Cormack et al. 2009): score = sum 1 / (RRF_K + rank)."""

MAX_K = 20
"""The most chunks one call returns."""

CANDIDATES = 50
"""How many chunks each side ranks before fusion (at least `MAX_K`)."""

PASSAGE_OPEN = "<retrieved_passage>"
PASSAGE_CLOSE = "</retrieved_passage>"

_KEYWORD = text(
    """
    WITH q AS (
        SELECT replace(plainto_tsquery('german'::regconfig, :query)::text, ' & ', ' | ')::tsquery
            AS terms
    )
    SELECT chunk.id
    FROM chunk, q
    WHERE chunk.tsv @@ q.terms
    ORDER BY ts_rank(chunk.tsv, q.terms) DESC, chunk.id
    LIMIT :limit
    """
)
_VECTOR = text(
    "SELECT id FROM chunk ORDER BY embedding <=> CAST(:vector AS vector), id LIMIT :limit"
)
_ROWS = text("SELECT id, source_ref, text FROM chunk WHERE id = ANY(:ids)").bindparams(
    bindparam("ids", type_=ARRAY(BigInteger))
)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    score: float
    """The RRF score (not normalised)."""
    source_ref: str
    text: str
    """The stored chunk text, unchanged. Untrusted: use `as_prompt_data()` in a prompt."""

    def as_prompt_data(self) -> str:
        """The chunk as untrusted data for a prompt: one `<retrieved_passage>` tag around JSON
        with no `<` or `>`, so nothing in the text or reference can close the wrapper."""
        body = json.dumps(
            {"chunk_id": self.chunk_id, "source_ref": self.source_ref, "text": self.text},
            ensure_ascii=False,
        )
        return PASSAGE_OPEN + body.replace("<", "\\u003c").replace(">", "\\u003e") + PASSAGE_CLOSE


@dataclass(frozen=True)
class RetrievalTrace:
    """One `retrieve` call, as the trace hooks see it. Counts only: never the query text."""

    latency_ms: int
    k: int
    query_chars: int
    returned: int
    keyword_hits: int
    vector_hits: int
    error: str | None
    """`<Class>: <text>` when the call failed (then `returned == 0`)."""
    scope: TraceScope | None = None


RetrievalTracer = Callable[[RetrievalTrace], None]


def rrf_merge(rankings: Sequence[Sequence[int]], *, rrf_k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal rank fusion: (chunk id, score), highest first, ties to the lower id."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def retrieve(
    query: str,
    k: int = 5,
    *,
    session: Session,
    embedder: QueryEmbedder,
    tracers: Sequence[RetrievalTracer] = (),
    scope: TraceScope | None = None,
) -> list[RetrievedChunk]:
    """The `k` chunks that best match `query`, best first. `ValueError` for `k` outside
    1..`MAX_K` or a blank query, before anything runs (and untraced)."""
    if not 1 <= k <= MAX_K:
        raise ValueError(f"k must be between 1 and {MAX_K}, not {k}")
    if not query.strip():
        raise ValueError("the query is blank")
    start = time.perf_counter()
    keyword: list[int] = []
    vector: list[int] = []
    found: list[RetrievedChunk] = []
    error: str | None = None
    try:
        query_vector = embedder.embed_query(query)
        keyword = list(session.scalars(_KEYWORD, {"query": query, "limit": CANDIDATES}))
        vector = list(
            session.scalars(_VECTOR, {"vector": _vector_text(query_vector), "limit": CANDIDATES})
        )
        found = _chunks(session, rrf_merge([keyword, vector])[:k])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        found = []
        raise
    finally:
        _trace(
            RetrievalTrace(
                latency_ms=round((time.perf_counter() - start) * 1000),
                k=k,
                query_chars=len(query),
                returned=len(found),
                keyword_hits=len(keyword),
                vector_hits=len(vector),
                error=error,
                scope=scope,
            ),
            tracers,
        )
    return found


def _vector_text(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _chunks(session: Session, merged: list[tuple[int, float]]) -> list[RetrievedChunk]:
    if not merged:
        return []
    rows = {row.id: row for row in session.execute(_ROWS, {"ids": [i for i, _ in merged]})}
    return [
        RetrievedChunk(chunk_id=i, score=score, source_ref=rows[i].source_ref, text=rows[i].text)
        for i, score in merged
    ]


def _trace(trace: RetrievalTrace, tracers: Sequence[RetrievalTracer]) -> None:
    """One log line (counts and the error class only), then each hook; a hook that raises is
    logged and skipped."""
    error_class = None if trace.error is None else trace.error.split(":", 1)[0]
    log.info(
        "retrieval latency_ms=%d k=%d query_chars=%d returned=%d keyword_hits=%d "
        "vector_hits=%d run_id=%s error=%s",
        trace.latency_ms, trace.k, trace.query_chars, trace.returned, trace.keyword_hits,
        trace.vector_hits, None if trace.scope is None else trace.scope.run_id, error_class,
    )  # fmt: skip
    for tracer in tracers:
        try:
            tracer(trace)
        except Exception:
            log.exception("retrieval trace hook failed")
