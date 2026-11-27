"""MKC-49: chunking per paragraph (§) with a source reference on every chunk (feature 70).

Whether a § is one chunk or one chunk per Absatz (with or without its heading line) is the
development agent's choice; these tests hold for both. A chunk keeps the source's lines
(whitespace inside a line may change); no chunk crosses a § boundary, no Absatz is lost, and
every chunk names the § it came from.
"""

import re

from tests.rag.conftest import LAW_TEXT

HEADING = re.compile(r"^§\s*(\d+[a-z]?)\b", re.M)


def _paragraphs(text: str) -> dict[str, str]:
    """The § blocks of a law text by their number, split at line-start headings only."""
    starts = [(m.start(), m.group(1)) for m in HEADING.finditer(text)]
    ends = [s for s, _ in starts[1:]] + [len(text)]
    return {num: text[start:end] for (start, num), end in zip(starts, ends, strict=True)}


def _lines(value: str) -> set[str]:
    return {" ".join(line.split()) for line in value.splitlines() if line.strip()}


def _home(chunk_text: str, paragraphs: dict[str, str]) -> list[str]:
    """The § blocks that hold every line of a chunk."""
    lines = _lines(chunk_text)
    return [num for num, block in paragraphs.items() if lines <= _lines(block)]


def _names(ref: str, num: str) -> bool:
    return re.search(rf"§\s*{re.escape(num)}(?![0-9a-z])", ref) is not None


def test_chunk_boundaries_follow_paragraphs() -> None:
    from mkc.rag.chunking import chunk_text

    paragraphs = _paragraphs(LAW_TEXT)
    assert list(paragraphs) == ["1", "2", "14a"]
    chunks = chunk_text(LAW_TEXT, source_id="musterg")
    assert chunks, "no chunks"

    homes = {}
    for chunk in chunks:
        home = _home(chunk.text, paragraphs)
        assert len(home) == 1, f"chunk crosses a § boundary: {chunk.text!r}"
        homes[chunk.ordinal] = home[0]

    # No Absatz is lost: each one is a line of a chunk of its own §.
    for num, block in paragraphs.items():
        own = set().union(*(_lines(c.text) for c in chunks if homes[c.ordinal] == num))
        for absatz in re.findall(r"^\(\d+\).*$", block, re.M):
            assert " ".join(absatz.split()) in own, f"§ {num}: lost {absatz!r}"

    # "§ 14a" inside § 2 (3) is a reference, not a heading: § 2 (3) stays in § 2.
    absatz = "(3) Steuerbare Verbrauchseinrichtung ist eine Wärmepumpe nach § 14a dieses Gesetzes."
    (holder,) = [c for c in chunks if absatz in _lines(c.text)]
    assert homes[holder.ordinal] == "2"
    assert _names(holder.source_ref, "2") and not _names(holder.source_ref, "14a")


def test_every_chunk_has_source_reference() -> None:
    from mkc.rag.chunking import chunk_text

    paragraphs = _paragraphs(LAW_TEXT)
    chunks = chunk_text(LAW_TEXT, source_id="musterg")
    assert chunks, "no chunks"
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.source_id == "musterg"
        assert chunk.source_ref.strip(), f"chunk without a source reference: {chunk!r}"
        (num,) = _home(chunk.text, paragraphs)
        assert _names(chunk.source_ref, num), (chunk.source_ref, num)
