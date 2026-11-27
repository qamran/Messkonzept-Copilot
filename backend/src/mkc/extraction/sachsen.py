"""SachsenNetze segmentation (feature 37, MKC-27, decision 74).

SachsenNetze ("Standard-Messkonzepte in Niederspannung", 09/2025): landscape pages with two
concepts side by side. Method: half page. Each page is cut at the middle of its width, and
each half is read on its own. A half is a concept when its first line is the heading
`Messkonzept <number>:` (`2-1:`, `2-1a:`). The cover, introduction and legend have no such
line; a body line that cites `Messkonzept 2-1:` is not the first line of its half. A half
whose title (the line below the heading) is `Nr. (tbd)` is a placeholder, not a concept.

A region's `bbox` is `(x0, top, x1, bottom)` in PDF points, origin top left, as for Berlin
(`mkc.extraction.segment`): the words and graphics that lie wholly inside the half, from the
heading down to the footer band. That leaves out the page background, the divider box that
crosses the middle, the frame lines that start above the heading, the page-wide rule, and the
footer text and logo (from 498 pt on a 540 pt page).
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, Any

import pdfplumber

if TYPE_CHECKING:
    # `segment` imports this module for `SEGMENTERS`, so the class is imported at call time.
    from mkc.extraction.segment import ConceptRegion

# Words whose tops differ by at most this many points are on one line (as for Berlin).
LINE_TOLERANCE = 3.0
# Content that starts at or below this share of the page height is footer (491.4 pt of 540,
# 09/2025 edition: the frames' bottom lines lie at 479.8 to 485.8 pt, the logo starts at
# 498 pt and the footer text at 509 pt).
FOOTER_BAND = 0.91
# The heading's two words: `Messkonzept` and a number with its colon (`2-1:`, `2-1a:`, `13:`).
HEADING = "Messkonzept"
NUMBER = re.compile(r"(\d{1,2}(?:-\d{1,2})?[a-z]?):")
# The title of a placeholder half (page 8 right of the 09/2025 edition).
PLACEHOLDER = re.compile(r"nr\.?\s*\(tbd\)", re.IGNORECASE)


def segment_sachsen(pdf: bytes) -> list[ConceptRegion]:
    regions: list[ConceptRegion] = []
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        for number, page in enumerate(document.pages, 1):
            width = float(page.width)
            for x0, x1 in ((0.0, width / 2), (width / 2, width)):
                region = _half(number, page, x0, x1)
                if region is not None:
                    regions.append(region)
    return regions


def _inside(o: Any, x0: float, x1: float) -> bool:
    return float(o["x0"]) >= x0 and float(o["x1"]) <= x1


def _lines(words: list[Any]) -> list[list[Any]]:
    """Words grouped into lines, top to bottom, each line left to right."""
    lines: list[list[Any]] = []
    for w in sorted(words, key=lambda w: (float(w["top"]), float(w["x0"]))):
        if lines and float(w["top"]) - float(lines[-1][0]["top"]) <= LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: float(w["x0"])) for line in lines]


def _half(number: int, page: Any, x0: float, x1: float) -> ConceptRegion | None:
    from mkc.extraction.segment import ConceptRegion

    footer = float(page.height) * FOOTER_BAND
    words = [w for w in page.extract_words() if _inside(w, x0, x1) and float(w["top"]) < footer]
    lines = _lines(words)
    if not lines or len(lines[0]) < 2 or lines[0][0]["text"] != HEADING:
        return None
    match = NUMBER.fullmatch(lines[0][1]["text"])
    if match is None:
        return None
    title = " ".join(w["text"] for w in lines[1]) if len(lines) > 1 else ""
    if PLACEHOLDER.fullmatch(title):
        return None
    top = float(lines[0][0]["top"])
    graphics = [
        o
        for o in (*page.rects, *page.lines, *page.curves, *page.images)
        if _inside(o, x0, x1) and top - LINE_TOLERANCE <= float(o["top"]) < footer
    ]
    content = [*words, *graphics]
    bbox = (
        round(min(float(o["x0"]) for o in content), 2),
        round(min(float(o["top"]) for o in content), 2),
        round(max(float(o["x1"]) for o in content), 2),
        round(max(float(o["bottom"]) for o in content), 2),
    )
    return ConceptRegion(page=number, bbox=bbox, number_hint=match.group(1))
