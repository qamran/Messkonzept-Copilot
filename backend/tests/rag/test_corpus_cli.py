"""MKC-49: `mkc corpus load` loads, chunks, embeds and indexes the sources of a file.

The CLI builds its fetcher and embedder with `mkc.rag.cli.make_fetcher` and
`mkc.rag.cli.make_embedder`; the tests replace both with fakes (no network, no model).
"""

from pathlib import Path

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


def test_mkc_corpus_load_indexes_a_synthetic_source(
    corpus_engine: Engine, sources_file: Path, fakes: FakeEmbedder
) -> None:
    from mkc.cli import app

    result = runner.invoke(app, ["corpus", "load", "--sources", str(sources_file)])
    assert result.exit_code == 0, result.output
    with corpus_engine.connect() as conn:
        documents = conn.execute(text("select count(*) from corpus_document")).scalar_one()
        chunks = conn.execute(text("select count(*) from chunk")).scalar_one()
        unindexed = conn.execute(
            text("select count(*) from chunk where embedding is null or tsv is null")
        ).scalar_one()
    assert documents == 2
    assert chunks >= 3
    assert unindexed == 0
    assert len(fakes.texts) == chunks


def test_mkc_corpus_load_refuses_a_bad_sources_file(
    corpus_engine: Engine, tmp_path: Path, fakes: FakeEmbedder
) -> None:
    from mkc.cli import app

    bad = tmp_path / "bad.yaml"
    bad.write_text("sources:\n  - id: x\n    licence: public-domain\n", encoding="utf-8")
    result = runner.invoke(app, ["corpus", "load", "--sources", str(bad)])
    assert result.exit_code == 2, result.output
    with corpus_engine.connect() as conn:
        assert conn.execute(text("select count(*) from corpus_document")).scalar_one() == 0
