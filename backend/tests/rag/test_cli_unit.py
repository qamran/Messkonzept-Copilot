"""MKC-49.6 unit tests for `mkc corpus load`: a subset of sources, the licence guard and a
failed fetch (nothing written), and the report it prints."""

import shutil
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text
from typer.testing import CliRunner

from tests.rag.conftest import FakeEmbedder, fake_fetcher

runner = CliRunner()


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, embedder: FakeEmbedder) -> FakeEmbedder:
    monkeypatch.setattr("mkc.rag.cli.make_embedder", lambda settings: embedder)
    monkeypatch.setattr("mkc.rag.cli.make_fetcher", lambda settings: fake_fetcher())
    return embedder


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"select count(*) from {table}")).scalar_one())


def test_load_one_source_and_print_the_report(
    corpus_engine: Engine, sources_file: Path, fakes: FakeEmbedder
) -> None:
    from mkc.cli import app

    args = ["corpus", "load", "--sources", str(sources_file), "--source", "musterg"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "musterg: 7 chunks" in result.output
    assert _count(corpus_engine, "corpus_document") == 1


def test_an_unknown_source_id_is_refused(
    corpus_engine: Engine, sources_file: Path, fakes: FakeEmbedder
) -> None:
    from mkc.cli import app

    args = ["corpus", "load", "--sources", str(sources_file), "--source", "nope"]
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "nope" in result.output


def test_a_cache_inside_the_repo_is_refused(
    corpus_engine: Engine, sources_file: Path, fakes: FakeEmbedder
) -> None:
    from mkc.cli import app
    from mkc.rag.loader import REPO_ROOT

    cache = REPO_ROOT / "backend" / ".mkc49-cli-cache-test"
    try:
        result = runner.invoke(
            app, ["corpus", "load", "--sources", str(sources_file), "--cache-dir", str(cache)]
        )
        assert result.exit_code == 2, result.output
        assert not cache.exists()
    finally:
        shutil.rmtree(cache, ignore_errors=True)  # a broken guard leaves nothing in the repo
    assert _count(corpus_engine, "corpus_document") == 0


def test_a_failed_fetch_writes_nothing(
    corpus_engine: Engine,
    sources_file: Path,
    fakes: FakeEmbedder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mkc.cli import app
    from mkc.rag.fetch import CorpusFetchError

    def fetch(source: Any) -> str:
        if source.id == "musterstadt-katalog":
            raise CorpusFetchError("PDF sources are not supported yet")
        return fake_fetcher()(source)

    monkeypatch.setattr("mkc.rag.cli.make_fetcher", lambda settings: fetch)
    result = runner.invoke(app, ["corpus", "load", "--sources", str(sources_file)])
    assert result.exit_code == 1
    assert "not supported" in result.output
    assert _count(corpus_engine, "corpus_document") == 0, "the whole load is one transaction"
