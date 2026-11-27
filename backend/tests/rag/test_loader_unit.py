"""MKC-49.5 unit tests for `load_corpus`: the guard runs before any fetch, a bad text or a
bad embedder reply stops the load, a reload replaces a source's chunks."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tests.rag.conftest import LAW_TEXT, TEXTS, FakeEmbedder, fake_fetcher


def _sources(sources_file: Path) -> list[Any]:
    from mkc.rag.sources import load_sources

    return load_sources(sources_file)


def test_the_guard_runs_before_any_fetch(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder, tmp_path: Path
) -> None:
    from mkc.rag.loader import CorpusLicenceError, load_corpus

    fetched: list[str] = []

    def fetcher(source: Any) -> str:
        fetched.append(source.id)
        return TEXTS[source.id]

    repo = tmp_path / "repo"
    repo.mkdir()
    with Session(corpus_engine) as session, pytest.raises(CorpusLicenceError):
        load_corpus(
            session,
            _sources(sources_file),
            embedder=embedder,
            fetcher=fetcher,
            cache_dir=repo / "c",
            repo_root=repo,
        )
    assert (fetched, embedder.texts) == ([], [])


def test_an_official_only_cache_inside_the_repo_is_allowed(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder, tmp_path: Path
) -> None:
    from mkc.rag.loader import check_cache_dir

    from mkc.rag.sources import LicenceClass

    official = [s for s in _sources(sources_file) if s.licence is LicenceClass.OFFICIAL]
    check_cache_dir(tmp_path / "c", official, repo_root=tmp_path)  # no error


def test_the_cache_is_read_instead_of_fetching_again(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder, tmp_path: Path
) -> None:
    from mkc.rag.loader import load_corpus

    calls: list[str] = []

    def fetcher(source: Any) -> str:
        calls.append(source.id)
        return TEXTS[source.id]

    cache = tmp_path / "cache"
    for _ in range(2):
        with Session(corpus_engine) as session, session.begin():
            load_corpus(
                session,
                _sources(sources_file),
                embedder=embedder,
                fetcher=fetcher,
                cache_dir=cache,
                repo_root=tmp_path / "repo",
            )
    assert sorted(calls) == ["musterg", "musterstadt-katalog"], "fetched once each"
    assert len(list(cache.iterdir())) == 2


def test_operator_text_is_chunked_by_sections(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder
) -> None:
    from mkc.rag.loader import load_corpus

    with Session(corpus_engine) as session, session.begin():
        report = load_corpus(
            session, _sources(sources_file), embedder=embedder, fetcher=fake_fetcher()
        )
    assert report == {"musterg": 7, "musterstadt-katalog": 2}
    with corpus_engine.connect() as conn:
        refs = conn.execute(
            text(
                "select c.source_ref from chunk c join corpus_document d on d.id = c.document_id "
                "where d.source_id = 'musterstadt-katalog' order by c.ordinal"
            )
        ).scalars()
        assert list(refs) == ["Abschnitt 1", "Abschnitt 2"]


def test_a_reload_replaces_the_chunks_of_a_changed_text(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder
) -> None:
    from mkc.rag.loader import load_corpus

    shorter = dict(TEXTS, musterg=LAW_TEXT.split("§ 2")[0])
    for texts in (TEXTS, shorter):
        with Session(corpus_engine) as session, session.begin():
            load_corpus(
                session, _sources(sources_file), embedder=embedder, fetcher=fake_fetcher(texts)
            )
    with corpus_engine.connect() as conn:
        refs = conn.execute(
            text(
                "select c.source_ref from chunk c join corpus_document d on d.id = c.document_id "
                "where d.source_id = 'musterg' order by c.ordinal"
            )
        ).scalars()
        assert list(refs) == ["§ 1 Abs. 1", "§ 1 Abs. 2"]


class ShortEmbedder(FakeEmbedder):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return super().embed(texts)[:-1]


@pytest.mark.parametrize("case", ["empty text", "short reply"])
def test_a_bad_text_or_reply_stops_the_load(
    corpus_engine: Engine, sources_file: Path, embedder: FakeEmbedder, case: str
) -> None:
    from mkc.rag.loader import CorpusLoadError, load_corpus

    from mkc.rag.embeddings import EMBEDDING

    texts = dict(TEXTS, musterg=" \n") if case == "empty text" else TEXTS
    used = ShortEmbedder("fake", EMBEDDING.dim) if case == "short reply" else embedder
    with Session(corpus_engine) as session, pytest.raises(CorpusLoadError):
        load_corpus(session, _sources(sources_file), embedder=used, fetcher=fake_fetcher(texts))
