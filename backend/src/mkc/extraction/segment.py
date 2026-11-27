"""Run-level `segment_document` (feature 28, MKC-21.3, decision 64).

Berlin (Stromnetz Berlin, "Messkonzepte", September 2026): one concept per page. A concept
page opens with `<number> <title>` (`1 Volleinspeisung`, `4.1 Überschusseinspeisung …`) on
the first line of the main column. A sidebar on the right (from about 77 % of the width)
repeats `Messkonzepte`, `Seite/Umfang` and the page number, level with the heading, so it is
left out. The cover, contents, table pages (rows such as `4.2 2RZ 60 A`) and the appendix
have no such first line.

A region's `bbox` is `(x0, top, x1, bottom)` in PDF points with the origin at the top left
(pdfplumber's convention, which `page.crop` takes): the main column from the heading down.
"""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pdfplumber

from mkc.extraction.fetch import SourceDocument
from mkc.harness.blobs import PREFIX, BlobStore

# Words left of this share of the page width are the main column.
MAIN_COLUMN = 0.75
# Words whose tops differ by at most this many points are on one line.
LINE_TOLERANCE = 3.0
# A concept number: 1, 4.1, 11.1, 2a. Not a year: at most two digits per part.
NUMBER = re.compile(r"\d{1,2}(?:\.\d{1,2})*[a-z]?")


class NoSegmenter(LookupError):
    """No segmenter for this operator yet (SachsenNetze comes in MKC-27)."""


@dataclass(frozen=True)
class ConceptRegion:
    page: int  # 1-based
    bbox: tuple[float, float, float, float]  # x0, top, x1, bottom in PDF points
    number_hint: str | None


def segment_document(doc: SourceDocument, *, store: BlobStore) -> list[ConceptRegion]:
    """The concept regions of `doc`, read from Storage by its hash."""
    segmenter = SEGMENTERS.get(doc.operator_id)
    if segmenter is None:
        raise NoSegmenter(doc.operator_id)
    return segmenter(store.get(PREFIX + doc.sha256))


def segment_berlin(pdf: bytes) -> list[ConceptRegion]:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        regions = (_berlin_page(number, page) for number, page in enumerate(document.pages, 1))
        return [r for r in regions if r is not None]


def _berlin_page(number: int, page: Any) -> ConceptRegion | None:
    limit = float(page.width) * MAIN_COLUMN
    words = [w for w in page.extract_words() if float(w["x0"]) < limit]
    if not words:
        return None
    top = min(float(w["top"]) for w in words)
    first = sorted(
        (w for w in words if float(w["top"]) - top <= LINE_TOLERANCE), key=lambda w: w["x0"]
    )
    if len(first) < 2 or not NUMBER.fullmatch(first[0]["text"]):
        return None
    if not first[1]["text"][0].isalpha():
        return None
    below = [w for w in words if float(w["top"]) >= top - LINE_TOLERANCE]
    graphics = [
        o
        for o in (*page.rects, *page.lines, *page.curves, *page.images)
        if float(o["x1"]) <= limit and float(o["top"]) >= top - LINE_TOLERANCE
    ]
    content = below + graphics
    bbox = (
        round(max(0.0, min(float(o["x0"]) for o in content)), 2),
        round(max(0.0, min(float(o["top"]) for o in content)), 2),
        round(min(limit, max(float(o["x1"]) for o in content)), 2),
        round(min(float(page.height), max(float(o["bottom"]) for o in content)), 2),
    )
    return ConceptRegion(page=number, bbox=bbox, number_hint=str(first[0]["text"]))


SEGMENTERS: dict[str, Callable[[bytes], list[ConceptRegion]]] = {
    "stromnetz-berlin": segment_berlin,
}
