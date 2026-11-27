"""MKC-49.1 unit tests: `load_sources` refuses every malformed sources file."""

from pathlib import Path

import pytest

GOOD = """\
sources:
  - id: musterg
    title: Mustergesetz
    source_type: law
    url: https://example.org/musterg
    version: "2026"
    licence: official
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_good_file_loads(tmp_path: Path) -> None:
    from mkc.rag.sources import LicenceClass, SourceType, load_sources

    (source,) = load_sources(_write(tmp_path, GOOD))
    assert source.id == "musterg"
    assert source.source_type is SourceType.LAW
    assert source.licence is LicenceClass.OFFICIAL
    assert source.url == "https://example.org/musterg"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("url: https://", "url: http://"),  # https only
        ("licence: official", "licence: restricted"),  # a law is official
        ("source_type: law", "source_type: blog"),  # unknown type
        ('    version: "2026"\n', ""),  # a field missing
        ("licence: official", "licence: official\n    text: Der Wortlaut"),  # never the text
        ("id: musterg", "id: Muster G"),  # ids are slugs
    ],
)
def test_a_bad_entry_is_refused(tmp_path: Path, old: str, new: str) -> None:
    from mkc.rag.sources import CorpusSourceError, load_sources

    assert old in GOOD
    with pytest.raises(CorpusSourceError):
        load_sources(_write(tmp_path, GOOD.replace(old, new)))


def test_an_operator_text_must_be_restricted(tmp_path: Path) -> None:
    from mkc.rag.sources import CorpusSourceError, load_sources

    body = GOOD.replace("source_type: law", "source_type: operator_text")
    with pytest.raises(CorpusSourceError):
        load_sources(_write(tmp_path, body))
    body = body.replace("licence: official", "licence: restricted")
    assert len(load_sources(_write(tmp_path, body))) == 1


@pytest.mark.parametrize(
    "body",
    ["", "sources: []\n", "- just a list\n", "sources: [", GOOD + GOOD.removeprefix("sources:\n")],
)
def test_a_bad_file_is_refused(tmp_path: Path, body: str) -> None:
    from mkc.rag.sources import CorpusSourceError, load_sources

    with pytest.raises(CorpusSourceError):
        load_sources(_write(tmp_path, body))


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    from mkc.rag.sources import CorpusSourceError, load_sources

    with pytest.raises(CorpusSourceError):
        load_sources(tmp_path / "nope.yaml")
