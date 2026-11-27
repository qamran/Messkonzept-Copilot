"""Chunking per paragraph with a source reference on every chunk (MKC-49.2, feature 70).

- `law` layout (laws as `mkc corpus load` gets them from gesetze-im-internet.de): a line
  that starts with `§` opens a paragraph; inside it, a line that starts with `(1)`, `(2)`, …
  opens an Absatz. Each Absatz is one chunk, with the paragraph's heading line first, so a
  chunk read alone still says where it is from. The reference reads `§ 14a Abs. 1`.
- `sections` layout (BNetzA decisions, operator texts): a short line that starts with a
  section number (`2`, `2.1`, `2.1.3`) opens a section; the reference reads `Abschnitt 2.1`.
  A `§` at the start of a line is not a boundary here: in PDF text it is often a wrapped
  citation.

Chunks never overlap and never cross a paragraph or section. Whitespace inside a line is
collapsed; nothing else is added to the text. A section longer than `MAX_CHUNK_CHARS` is
split at blank lines (each piece repeats the heading line).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

Layout = Literal["law", "sections"]

MAX_CHUNK_CHARS = 4000
"""About 1,000 tokens of German text: well inside the embedding model's context."""

PREAMBLE_REF = "Vorspann"
"""The reference of text before the first paragraph or section."""

_PARAGRAPH = re.compile(r"^(§§?)\s*(\d+[a-z]?)\b(.*)$")
_ABSATZ = re.compile(r"^\((\d+[a-z]?)\)")
_SECTION = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+\S")
_SECTION_MAX_LINE = 120
"""A numbered line longer than this is body text (a list item), not a section heading."""
_LAW_REF_TAIL = re.compile(r"^((?:\s*(?:bis|und|,)\s*\d+[a-z]?)*)")


@dataclass(frozen=True)
class Chunk:
    source_id: str
    ordinal: int
    source_ref: str
    text: str


@dataclass
class _Block:
    ref: str
    heading: str | None
    lines: list[str]


def _clean(line: str) -> str:
    return " ".join(line.split())


def chunk_text(text: str, *, source_id: str, layout: Layout = "law") -> list[Chunk]:
    """The chunks of one source's plain text, numbered 0, 1, 2, … in text order."""
    lines = [_clean(line) for line in text.splitlines()]
    blocks = _law_blocks(lines) if layout == "law" else _section_blocks(lines)
    pieces = [(b.ref, piece) for b in blocks for piece in _pieces(b)]
    return [
        Chunk(source_id=source_id, ordinal=i, source_ref=ref, text=body)
        for i, (ref, body) in enumerate(pieces)
    ]


def _law_ref(match: re.Match[str]) -> str:
    """`§ 14a` or, for a heading like `§§ 7 bis 9 (weggefallen)`, `§§ 7 bis 9`."""
    sign, number, rest = match.groups()
    tail = _LAW_REF_TAIL.match(rest)
    extra = _clean(tail.group(1)) if sign == "§§" and tail else ""
    return f"{sign} {number}" + (f" {extra}" if extra else "")


def _law_blocks(lines: list[str]) -> list[_Block]:
    """One block per Absatz (or per paragraph without numbered Absätze)."""
    blocks: list[_Block] = []
    preamble: list[str] = []
    heading: str | None = None
    paragraph_ref = ""
    current: _Block | None = None
    for line in lines:
        if not line:
            continue
        paragraph = _PARAGRAPH.match(line)
        if paragraph:
            heading = line
            paragraph_ref = _law_ref(paragraph)
            current = _Block(paragraph_ref, heading, [])
            blocks.append(current)
            continue
        if current is None:
            preamble.append(line)
            continue
        absatz = _ABSATZ.match(line)
        if absatz:
            ref = f"{paragraph_ref} Abs. {absatz.group(1)}"
            if not current.lines and current.ref == paragraph_ref:
                current.ref = ref  # the paragraph's first Absatz takes over its block
            else:
                current = _Block(ref, heading, [])
                blocks.append(current)
        current.lines.append(line)
    if preamble:
        blocks.insert(0, _Block(PREAMBLE_REF, None, preamble))
    return blocks


def _section_blocks(lines: list[str]) -> list[_Block]:
    """One block per numbered section; blank lines are kept as split points."""
    blocks: list[_Block] = []
    current: _Block | None = None
    for line in lines:
        section = _SECTION.match(line) if len(line) <= _SECTION_MAX_LINE else None
        if section:
            current = _Block(f"Abschnitt {section.group(1)}", line, [])
            blocks.append(current)
            continue
        if current is None:
            if not line:
                continue
            current = _Block(PREAMBLE_REF, None, [])
            blocks.append(current)
        current.lines.append(line)
    return blocks


def _pieces(block: _Block) -> Iterator[str]:
    """The block's text, split at blank lines into pieces of at most `MAX_CHUNK_CHARS`."""
    head = [block.heading] if block.heading else []
    paragraphs: list[list[str]] = [[]]
    for line in block.lines:
        if line:
            paragraphs[-1].append(line)
        elif paragraphs[-1]:
            paragraphs.append([])
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        if head:
            yield "\n".join(head)
        return
    piece: list[str] = []
    for paragraph in paragraphs:
        candidate = [*piece, *paragraph]
        if piece and len("\n".join(head + candidate)) > MAX_CHUNK_CHARS:
            yield "\n".join(head + piece)
            piece = list(paragraph)
        else:
            piece = candidate
    yield "\n".join(head + piece)
