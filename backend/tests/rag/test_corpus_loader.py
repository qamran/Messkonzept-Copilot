"""MKC-49: `load_corpus` loads, chunks, embeds and indexes sources into Postgres (features
69, 70), and never writes a non-official text inside the repo.

The fetcher and the embedder are fakes from tests/rag/conftest.py: no network, no model.
"""

import shutil
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tests.rag.conftest import TEXTS, FakeEmbedder, fake_fetcher

REPO = Path(__file__).resolve().parents[3]


def _load(engine: Engine, sources_file: Path, embedder: FakeEmbedder, **kwargs: object) -> None:
    from mkc.rag.loader import load_corpus
    from mkc.rag.sources import load_sources

    sources = load_sources(sources_file)
    with Session(engine) as session, session.begin():
        load_corpus(session, sources, embedder=embedder, fetcher=fake_fetcher(), **kwargs)


def _vector(value: str) -> list[float]:
    return [float(x) for x in value.strip("[]").split(",")]


def test_load_corpus_stores_documents_chunks_and_embeddings(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder
) -> None:
    _load(corpus_engine, sources_file, embedder)
    with corpus_engine.connect() as conn:
        documents = conn.execute(
            text("select source_id, source_type, url, version, licence from corpus_document")
        ).all()
        rows = conn.execute(
            text("select text, embedding::text, vector_dims(embedding) from chunk order by id")
        ).all()
    assert sorted(d.source_id for d in documents) == ["musterg", "musterstadt-katalog"]
    by_id = {d.source_id: d for d in documents}
    assert by_id["musterg"].licence == "official"
    assert by_id["musterg"].source_type == "law"
    assert by_id["musterstadt-katalog"].licence == "restricted"
    assert by_id["musterg"].url == "https://example.org/musterg"
    assert by_id["musterg"].version == "2026-11-27"

    assert len(rows) >= 3, "the law text alone has three §"
    assert sorted(embedder.texts) == sorted(r.text for r in rows), "each chunk embedded once"
    for row in rows:
        assert row.vector_dims == embedder.dim
        expected = embedder.vector(row.text)
        assert _vector(row.embedding) == pytest.approx(expected, abs=1e-3)


def test_every_stored_chunk_has_source_reference(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder
) -> None:
    _load(corpus_engine, sources_file, embedder)
    with corpus_engine.connect() as conn:
        rows = conn.execute(
            text(
                "select c.source_ref, c.text, d.source_id, d.url, d.version, d.licence "
                "from chunk c left join corpus_document d on d.id = c.document_id"
            )
        ).all()
    assert rows
    for row in rows:
        assert row.source_id is not None, f"chunk without a document: {row.text!r}"
        assert row.source_ref and row.source_ref.strip(), f"no source_ref: {row.text!r}"
        assert row.url and row.version and row.licence
        assert row.text.strip() and row.text.split()[0] in TEXTS[row.source_id]


def test_chunks_are_indexed_for_german_full_text(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder
) -> None:
    _load(corpus_engine, sources_file, embedder)
    with corpus_engine.connect() as conn:
        # "Messstellenbetreibern" in the text is found by its stem "Messstellenbetreiber".
        hits = conn.execute(
            text(
                "select source_ref from chunk "
                "where tsv @@ plainto_tsquery('german', 'Messstellenbetreiber')"
            )
        ).scalars()
        refs = list(hits)
    assert any("14a" in ref for ref in refs), refs


def test_loading_twice_keeps_one_copy(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder
) -> None:
    _load(corpus_engine, sources_file, embedder)
    with corpus_engine.connect() as conn:
        first = conn.execute(text("select count(*) from chunk")).scalar_one()
    _load(corpus_engine, sources_file, embedder)
    with corpus_engine.connect() as conn:
        documents = conn.execute(text("select count(*) from corpus_document")).scalar_one()
        second = conn.execute(text("select count(*) from chunk")).scalar_one()
    assert (documents, second) == (2, first)


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


def test_non_official_sources_not_written_to_repo(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder, tmp_path: Path
) -> None:
    from mkc.rag.loader import CorpusLicenceError

    # A stand-in repo: a cache inside it must be refused for a restricted (non-official) text.
    repo = tmp_path / "repo"
    repo.mkdir()
    for cache in (repo / "cache", tmp_path / "elsewhere" / ".." / "repo" / "data"):
        with pytest.raises(CorpusLicenceError):
            _load(corpus_engine, sources_file, embedder, cache_dir=cache, repo_root=repo)
        assert _files(repo) == [], f"written inside the repo: {_files(repo)}"

    # The guard refuses before anything is written, official texts included.
    # The default repo root is this repo; the test removes the folder if the guard fails.
    inside = REPO / "backend" / "data" / "mkc49-corpus-cache-test"
    try:
        with pytest.raises(CorpusLicenceError):
            _load(corpus_engine, sources_file, embedder, cache_dir=inside)
        assert _files(inside) == []
    finally:
        shutil.rmtree(inside, ignore_errors=True)

    # A cache outside the repo is fine; the restricted text is loaded and only lives there.
    outside = tmp_path / "cache"
    _load(corpus_engine, sources_file, embedder, cache_dir=outside, repo_root=repo)
    with corpus_engine.connect() as conn:
        licence = conn.execute(
            text("select licence from corpus_document where source_id = 'musterstadt-katalog'")
        ).scalar_one()
    assert licence == "restricted"
    assert _files(repo) == []
