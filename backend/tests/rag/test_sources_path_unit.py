"""MKC-50.4 (development agent): where `load_sources` and `mkc corpus load` find the sources
file. The image installs `mkc` into the venv, so `DEFAULT_SOURCES_PATH` (next to the source
tree) does not exist there; the image ships the file at `/app/data/corpus_sources.yaml`.
Order: `MKC_CORPUS_SOURCES_FILE`, then the source-tree file, then the image path."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.rag.conftest import SOURCES_YAML


def test_the_setting_names_the_sources_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.rag.sources import load_sources, sources_path

    path = tmp_path / "corpus.yaml"
    path.write_text(SOURCES_YAML, encoding="utf-8")
    monkeypatch.setenv("MKC_CORPUS_SOURCES_FILE", str(path))
    assert sources_path() == path
    assert [s.id for s in load_sources()] == ["musterg", "musterstadt-katalog"]


def test_without_the_setting_the_source_tree_file_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mkc.rag.sources import DEFAULT_SOURCES_PATH, sources_path

    monkeypatch.delenv("MKC_CORPUS_SOURCES_FILE", raising=False)
    assert DEFAULT_SOURCES_PATH.is_file()
    assert sources_path() == DEFAULT_SOURCES_PATH


def test_in_the_image_the_shipped_file_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.rag import sources

    monkeypatch.delenv("MKC_CORPUS_SOURCES_FILE", raising=False)
    monkeypatch.setattr(sources, "DEFAULT_SOURCES_PATH", tmp_path / "missing.yaml")
    assert sources.IMAGE_SOURCES_PATH.as_posix() == "/app/data/corpus_sources.yaml"
    assert sources.sources_path() == sources.IMAGE_SOURCES_PATH


def test_the_path_is_read_at_call_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Not frozen as a default argument when the module is imported."""
    from mkc.rag.sources import CorpusSourceError, load_sources

    monkeypatch.setenv("MKC_CORPUS_SOURCES_FILE", str(tmp_path / "nowhere.yaml"))
    with pytest.raises(CorpusSourceError, match=r"nowhere.yaml"):
        load_sources()


def test_the_cli_uses_the_setting_without_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.cli import app

    monkeypatch.setenv("MKC_CORPUS_SOURCES_FILE", str(tmp_path / "nowhere.yaml"))
    result = CliRunner().invoke(app, ["corpus", "load", "--source", "musterg"])
    assert result.exit_code == 2
    assert "nowhere.yaml" in result.output
