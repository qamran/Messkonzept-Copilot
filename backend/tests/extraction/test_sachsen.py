"""MKC-27: SachsenNetze segmentation (feature 37), lane A2.

Pinned interface (module `mkc.extraction.sachsen`):

    segment_sachsen(pdf: bytes) -> list[ConceptRegion]

registered in `SEGMENTERS["sachsennetze"]` (`mkc.extraction.segment`), so
`segment_document(doc, store=...)` dispatches `operator_id == "sachsennetze"` to it.

Layout (the real catalogue, 09/2025, see `sachsen_pdf.py`): landscape pages, pages 3 to 8 with
two concepts side by side. Each half opens with `Messkonzept <number>:`. The `number_hint` is
the number without the colon (`2-1`, `2-1a`). The cover, contents, legend and footers give no
region. A half that is only a placeholder (`Messkonzept 13:`, title `Nr. (tbd)`, no figure)
is not a concept: the design and the ticket count 11 concepts, the PDF has 12 halves.
"""

from datetime import UTC, datetime
from typing import Any

from mkc.harness.blobs import PREFIX
from tests.extraction.conftest import MemoryStore
from tests.extraction.sachsen_pdf import (
    FOOTER_TOP,
    HEIGHT,
    WIDTH,
    footer,
    half,
    make_landscape_pdf,
    sachsen_pages,
)

MID = WIDTH / 2


def _regions() -> list[Any]:
    from mkc.extraction.sachsen import segment_sachsen

    return segment_sachsen(make_landscape_pdf(sachsen_pages()))


def test_a_two_up_page_gives_two_regions_in_reading_order() -> None:
    from mkc.extraction.segment import ConceptRegion

    regions = _regions()
    assert all(isinstance(r, ConceptRegion) for r in regions)
    assert [(r.page, r.number_hint) for r in regions] == [
        (3, "2-1"),
        (3, "2-1a"),
        (4, "2-2"),
        (4, "2-2a"),
        (5, "3-5"),
    ]


def test_the_two_regions_of_a_page_are_disjoint_halves() -> None:
    regions = _regions()
    for left, right in zip(regions[0:4:2], regions[1:4:2], strict=True):
        assert left.page == right.page
        assert left.bbox[2] <= MID <= right.bbox[0], "left ends before the middle, right after"
        assert left.bbox[0] < 20, "the left region starts at its heading (x = 11 pt)"
        assert 490 < right.bbox[0] < 510, "the right region starts at its heading (x = 499 pt)"
        assert right.bbox[2] <= WIDTH


def test_a_region_covers_its_heading_and_body_but_not_the_footer() -> None:
    for r in _regions():
        x0, top, x1, bottom = r.bbox
        assert 20 <= top <= 35, "starts at the heading (glyph top about 30 pt)"
        assert bottom >= 440, "reaches the last body lines (y = 445 pt)"
        assert bottom < FOOTER_TOP, "the footer line is not part of the region"
        assert x1 - x0 > 200 and bottom <= HEIGHT


def test_non_concept_pages_give_no_region() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    pages = sachsen_pages()
    cover_contents_legend = [pages[0], pages[1], pages[5]]
    assert segment_sachsen(make_landscape_pdf(cover_contents_legend)) == []


def test_a_placeholder_half_is_not_a_concept() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    pdf = make_landscape_pdf(
        [
            [
                *half(11.0, "13", "Nr. (tbd)", figure=False),
                *half(499.0, "13", "Nr. (tbd)", figure=False),
            ]
        ]
    )
    assert segment_sachsen(pdf) == []
    assert "13" not in [r.number_hint for r in _regions()]


def test_a_body_line_that_cites_a_concept_is_not_a_heading() -> None:
    # Page 3's right half cites `Messkonzept 2-1:` far below its heading (as does the real one).
    hints = [r.number_hint for r in _regions()]
    assert hints.count("2-1") == 1


def test_a_page_with_one_concept_gives_one_region() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    pdf = make_landscape_pdf([[*half(11.0, "3-1", "Eigenverbrauch"), *footer(3)]])
    (region,) = segment_sachsen(pdf)
    assert region.page == 1 and region.number_hint == "3-1"
    assert region.bbox[2] <= MID


def test_segment_document_dispatches_sachsennetze_to_the_new_segmenter() -> None:
    from mkc.extraction.fetch import SourceDocument
    from mkc.extraction.sachsen import segment_sachsen
    from mkc.extraction.segment import SEGMENTERS, segment_document

    assert SEGMENTERS["sachsennetze"] is segment_sachsen
    store = MemoryStore()
    pdf = make_landscape_pdf(sachsen_pages())
    ref = store.put(pdf)
    doc = SourceDocument(
        operator_id="sachsennetze", url="https://x.example/a.pdf",
        sha256=ref.removeprefix(PREFIX), fetched_at=datetime.now(UTC), page_count=6,
        edition=1, new_edition=False,
    )  # fmt: skip
    assert segment_document(doc, store=store) == segment_sachsen(pdf)
    assert len(segment_document(doc, store=store)) == 5


def test_berlin_is_still_dispatched_to_berlin() -> None:
    from mkc.extraction.segment import SEGMENTERS, segment_berlin

    assert SEGMENTERS["stromnetz-berlin"] is segment_berlin
