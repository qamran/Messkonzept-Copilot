"""`extract_text` (feature 29, MKC-22.1, decision 76): the text fields of one concept region.

Read by layout, not by a model: pdfplumber's text lines inside the region's bbox, sorted top
to bottom, then

- `title`: the first line without its concept number, plus the lines below it in the same
  type size that follow at a line's pitch (a wrapped heading), up to `Anwendung:`;
- `applications`: the bullets of the list after `Anwendung:` that are not `LBS` bullets;
- `stated_lbs`: every `LBS` bullet: 13 ASCII digits (spaces between them allowed) and the
  text in brackets right after them. A code is kept as printed, also with a wrong check
  digit: it is what the operator stated, and `validate_draft` (MKC-28) judges it;
- `footnotes`: each line that starts with `*n)`, with the lines that go on below it.

A bullet or footnote that wraps goes on in the next line, at a line's pitch (at most 1.6
times the type size below), indented past the bullet sign or level with the footnote marker.
Diagram labels (`Z 1`, `G`, `*1` without a bracket) match none of the rules.
"""

import io
import math
import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import pdfplumber
from pydantic import BaseModel, ConfigDict

from mkc.extraction.cleantext import clean, join_lines
from mkc.extraction.segment import ConceptRegion

# The next line of a wrapped heading, bullet or footnote starts within this many type sizes.
PITCH = 1.6
_NUMBER = re.compile(r"^\d{1,2}(?:\.\d{1,2})*[a-z]?\s+")
_APPLICATIONS = re.compile(r"^Anwendung\s*:")
_BULLET = re.compile(r"^[•▪·]\s*")
_FOOTNOTE = re.compile(r"^\*\s?\d+\)")
_LBS = re.compile(r"^LBS\s*((?:[0-9]\s*){12}[0-9])(?![0-9])\s*(?:\(([^)]*)\)?)?")


class StatedLbs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str  # 13 digits, spaces removed
    condition: str | None  # the text in brackets after the code


class TextFields(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    applications: list[str]
    footnotes: list[str]
    stated_lbs: list[StatedLbs]


class PageNotFound(ValueError):
    """The page number is outside the document."""


@dataclass(frozen=True)
class _Line:
    text: str
    x0: float
    top: float
    size: float


def extract_text(pdf: bytes, region: ConceptRegion) -> TextFields:
    """The text fields of `region`; only words inside its bbox count."""
    return read_page(pdf, region.page, region.bbox)


def read_page(
    pdf: bytes, page: int, bbox: tuple[float, float, float, float] | None = None
) -> TextFields:
    """The text fields of `page` (1-based) inside `bbox` (`x0, top, x1, bottom`, top-left
    origin), or of the whole page without one. The bbox is clipped to the page."""
    return fields_of(page_lines(pdf, page, bbox))


def page_lines(
    pdf: bytes, page: int, bbox: tuple[float, float, float, float] | None = None
) -> list[_Line]:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        if not 1 <= page <= len(document.pages):
            raise PageNotFound(f"page {page} is not in the document ({len(document.pages)} pages)")
        view = document.pages[page - 1]
        if bbox is not None:
            view = view.crop(_clip(bbox, float(view.width), float(view.height)))
        raw = view.extract_text_lines(return_chars=True)
    lines = [_line(r) for r in raw]
    return sorted((x for x in lines if x.text), key=lambda x: (round(x.top, 1), x.x0))


def fields_of(lines: list[_Line]) -> TextFields:
    title, rest = _title(lines)
    after = next((i + 1 for i, x in enumerate(rest) if _APPLICATIONS.match(x.text)), None)
    applications: list[str] = []
    stated: list[StatedLbs] = []
    for start, end, text in _bullets(rest):
        found = _LBS.match(text)
        if found:
            code = re.sub(r"\s", "", found.group(1))
            condition = clean(found.group(2) or "") or None
            stated.append(StatedLbs(code=code, condition=condition))
        elif start == after:
            applications.append(text)
        if start == after:
            after = end  # the list after `Anwendung:` goes on with the next bullet
    return TextFields(
        title=title, applications=applications, footnotes=_footnotes(rest), stated_lbs=stated
    )


def _title(lines: list[_Line]) -> tuple[str, list[_Line]]:
    if not lines:
        return "", []
    first = lines[0]
    parts = [_NUMBER.sub("", first.text, count=1)]
    end = 1
    for prev, line in pairwise(lines):
        if (
            _APPLICATIONS.match(line.text)
            or abs(line.size - first.size) > 0.5
            or not _follows(prev, line)
        ):
            break
        parts.append(line.text)
        end += 1
    return join_lines(parts), lines[end:]


def _bullets(lines: list[_Line]) -> list[tuple[int, int, str]]:
    """(first line, line after it, the text without the sign, wrapped lines joined)."""
    out: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _BULLET.match(line.text):
            i += 1
            continue
        parts, j = [_BULLET.sub("", line.text, count=1)], i + 1
        while (
            j < len(lines)
            and not _BULLET.match(lines[j].text)
            and lines[j].x0 > line.x0 + 2
            and _follows(lines[j - 1], lines[j])
        ):
            parts.append(lines[j].text)
            j += 1
        out.append((i, j, join_lines(parts)))
        i = j
    return out


def _footnotes(lines: list[_Line]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _FOOTNOTE.match(line.text):
            i += 1
            continue
        parts, j = [line.text], i + 1
        while (
            j < len(lines)
            and not _FOOTNOTE.match(lines[j].text)
            and lines[j].x0 >= line.x0 - 2
            and _follows(lines[j - 1], lines[j])
        ):
            parts.append(lines[j].text)
            j += 1
        out.append(join_lines(parts))
        i = j
    return out


def _follows(prev: _Line, line: _Line) -> bool:
    return 0 < line.top - prev.top <= PITCH * prev.size


def _line(raw: dict[str, Any]) -> _Line:
    chars = raw.get("chars") or []
    size = max((float(c["size"]) for c in chars), default=float(raw["bottom"]) - float(raw["top"]))
    return _Line(
        text=clean(str(raw["text"])), x0=float(raw["x0"]), top=float(raw["top"]), size=size
    )


def _clip(
    bbox: tuple[float, float, float, float], width: float, height: float
) -> tuple[float, float, float, float]:
    if not all(math.isfinite(v) for v in bbox):
        raise ValueError(f"the bbox {bbox} has a value that is no finite number")
    x0, top = max(0.0, bbox[0]), max(0.0, bbox[1])
    x1, bottom = min(width, bbox[2]), min(height, bbox[3])
    if x0 >= x1 or top >= bottom:
        raise ValueError(f"the bbox {bbox} does not overlap the page (0, 0, {width}, {height})")
    return x0, top, x1, bottom
