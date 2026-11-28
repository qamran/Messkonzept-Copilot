"""MKC-50 live check of the retriever: the real EnWG § 14a page and the synthetic law of
`conftest.py`, embedded with the real model into the test database, then two real query
embeddings. Costs a fraction of a cent.

Run on purpose, from `backend/`:
`uv run --env-file .env pytest -m live tests/rag/test_retriever_live.py -s`
(`MKC_OPENROUTER_API_KEY` in `.env`; the test sets live mode itself).
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mkc.config import Settings
from tests.rag.conftest import fake_fetcher

if TYPE_CHECKING:
    from mkc.rag.sources import CorpusSource

pytestmark = pytest.mark.live


def test_live_retrieval_over_enwg_14a(corpus_engine: Engine) -> None:
    from mkc.rag.embeddings import ProviderEmbedder
    from mkc.rag.fetch import http_fetcher
    from mkc.rag.loader import load_corpus
    from mkc.rag.retriever import RetrievalTrace, retrieve
    from mkc.rag.sources import load_sources
    from tests.rag.conftest import TEXTS

    by_id = {s.id: s for s in load_sources()}
    enwg = by_id["enwg-14a"]
    synthetic = [s for s in _synthetic_sources() if s.id == "musterg"]
    embedder = ProviderEmbedder.from_settings(Settings(model_mode="live"))
    with Session(corpus_engine) as session, session.begin():
        load_corpus(session, [enwg], embedder=embedder, fetcher=http_fetcher())
        load_corpus(session, synthetic, embedder=embedder, fetcher=fake_fetcher(TEXTS))
    loaded = (embedder.input_tokens, embedder.cost_eur)

    seen: list[RetrievalTrace] = []
    with Session(corpus_engine) as session:
        question = "Darf der Netzbetreiber meine Wärmepumpe bei drohender Überlastung drosseln?"
        found = retrieve(question, 3, session=session, embedder=embedder, tracers=[seen.append])
        by_ref = retrieve("§ 14a", 3, session=session, embedder=embedder)
    print(
        f"load: tokens {loaded[0]}, cost {loaded[1]:.8f} EUR; "
        f"total with 2 queries: tokens {embedder.input_tokens}, cost {embedder.cost_eur:.8f} EUR"
    )
    print(f"question -> {[c.source_ref for c in found]}, latency {seen[0].latency_ms} ms")
    print(f"'§ 14a' -> {[c.source_ref for c in by_ref]}")
    assert found[0].source_ref.startswith("§ 14a")
    assert by_ref[0].source_ref.startswith("§ 14a")
    assert seen[0].latency_ms > 0 and seen[0].vector_hits > 0


def _synthetic_sources() -> "Sequence[CorpusSource]":
    import tempfile
    from pathlib import Path

    from mkc.rag.sources import load_sources
    from tests.rag.conftest import SOURCES_YAML

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "sources.yaml"
        path.write_text(SOURCES_YAML, encoding="utf-8")
        return load_sources(path)
