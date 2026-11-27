"""MKC-21.3 (development agent): the Berlin heading rule on the cases of the real catalogue.

`segment_berlin(pdf) -> list[ConceptRegion]` works on the bytes; `segment_document` reads
them from Storage and picks the segmenter by operator.
"""

from datetime import UTC, datetime

import pytest

from tests.extraction.conftest import MemoryStore, Side, berlin_pages, make_pdf

A4 = (595.0, 842.0)
SIDEBAR = [Side("Messkonzepte"), Side("Seite/Umfang"), Side("5/33")]


def _hints(pages: list[list[str]]) -> list[str | None]:
    from mkc.extraction.segment import segment_berlin

    return [r.number_hint for r in segment_berlin(make_pdf(pages, size=A4))]


@pytest.mark.parametrize(
    "first_line",
    [
        "4.2 2RZ 60 A 2RZ 100A 2RZ (Wandler)",  # a table row (page 5)
        "5 / 5.1 / 5.2 / 6 / 6.2 9992 00000 008 4",  # an LBS table row (page 7)
        "Messkonzept Erzeugungsmessung (Z2)",  # a table header (page 5)
        "Messkonzept 1",  # the old assumption is not a heading either
        "2026 Ausgabe September",  # a year, not a concept number
        "1",  # a number with no title
    ],
)
def test_a_first_line_that_is_no_heading_gives_no_region(first_line: str) -> None:
    assert _hints([[first_line, "Anwendung:", *SIDEBAR]]) == []


@pytest.mark.parametrize(
    ("first_line", "hint"),
    [
        ("1 Volleinspeisung", "1"),
        ("4.1 Ueberschusseinspeisung mit Erzeugungsmessun-", "4.1"),
        ("11.1 Ueberschusseinspeisung und steuerbare", "11.1"),
        ("6.3 Gemeinschaftliche Gebaeudeversorgung (GGV)", "6.3"),
    ],
)
def test_a_heading_next_to_the_sidebar_gives_its_number(first_line: str, hint: str) -> None:
    assert _hints([[first_line, "Anwendung:", *SIDEBAR]]) == [hint]


def test_a_heading_lower_on_the_page_is_not_a_concept() -> None:
    assert _hints([["Befestigung der Messtechnik", "3 Ueberschusseinspeisung", *SIDEBAR]]) == []


def test_the_region_is_the_main_column_from_the_heading_down() -> None:
    from mkc.extraction.segment import segment_berlin

    (region,) = segment_berlin(make_pdf([["7 Weitergabe", "Anwendung:", *SIDEBAR]], size=A4))
    x0, top, x1, bottom = region.bbox
    assert region.page == 1
    assert 60 < x0 <= 72, "starts at the main column's left edge"
    assert x1 < 461, "the sidebar is not part of the region"
    assert 72 - 14 < top < 72, "starts at the heading (origin top left, baseline at 72 pt)"
    assert bottom > top + 18, "covers the lines below the heading"


def test_segment_document_refuses_an_operator_without_a_segmenter() -> None:
    from mkc.extraction.fetch import SourceDocument
    from mkc.extraction.segment import NoSegmenter, segment_document

    store = MemoryStore()
    ref = store.put(make_pdf(berlin_pages(["1"])))
    doc = SourceDocument(
        operator_id="sachsennetze", url="https://x.example/a.pdf",
        sha256=ref.rsplit(":", 1)[1], fetched_at=datetime.now(UTC), page_count=4,
        edition=1, new_edition=False,
    )  # fmt: skip
    with pytest.raises(NoSegmenter):
        segment_document(doc, store=store)


class _Page:
    """A pdfplumber-like page: words and one drawing that reaches past the column edge."""

    def __init__(self) -> None:
        self.width, self.height = 595.0, 842.0
        self.lines: list[dict[str, float]] = []
        self.curves: list[dict[str, float]] = []
        self.images: list[dict[str, float]] = []
        self.rects = [{"x0": 403.0, "x1": 461.0, "top": 440.0, "bottom": 470.0}]  # page 27

    def extract_words(self) -> list[dict[str, object]]:
        word = {"top": 123.6, "bottom": 137.6}
        return [
            {**word, "x0": 56.6, "x1": 72.2, "text": "6.3"},
            {**word, "x0": 99.3, "x1": 240.0, "text": "Gemeinschaftliche"},
            {**word, "x0": 460.8, "x1": 535.6, "text": "Messkonzepte"},
        ]


def test_a_drawing_that_starts_in_the_column_is_kept_whole() -> None:
    from mkc.extraction.segment import _berlin_page

    region = _berlin_page(27, _Page())
    assert region is not None
    assert region.bbox == (56.6, 123.6, 461.0, 470.0)
