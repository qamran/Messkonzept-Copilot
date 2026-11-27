"""MKC-21: `segment_document` (feature 28): Berlin, one concept per page.

Pinned interface (module `mkc.extraction.segment`):

    segment_document(doc: SourceDocument, *, store: BlobStore) -> list[ConceptRegion]
    ConceptRegion(page: int (1-based), bbox: (x0, y0, x1, y1) in PDF points,
                  number_hint: str | None)

It reads the PDF from Storage by the document's hash and picks the segmenter by
`doc.operator_id` (Berlin here; SachsenNetze comes in MKC-27, lane A2).

Assumption (lane file): a Berlin concept page starts with the heading `Messkonzept <n>`; the
cover, contents and appendix pages are not concepts, and a body line that cites another
concept is not a heading. The live test checks this against the real catalogue.
"""

from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.blobs import PREFIX
from tests.extraction.conftest import (
    OPERATOR_ID,
    URL_OK,
    FakeGet,
    MemoryStore,
    berlin_pages,
    make_pdf,
    operators,
)

A4 = (595.0, 842.0)


def _fetch(sessions: sessionmaker[Session], store: MemoryStore, *pdfs: bytes) -> list[Any]:
    from mkc.extraction.fetch import fetch_document

    get = FakeGet([(URL_OK, pdf) for pdf in pdfs])
    return [
        fetch_document(OPERATOR_ID, sessions=sessions, store=store, get=get, operators=operators())
        for _ in pdfs
    ]


def test_berlin_segmentation_one_region_per_concept_page(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.segment import ConceptRegion, segment_document

    pdf = make_pdf(berlin_pages(["1", "2a", "3"]), size=A4)
    (doc,) = _fetch(sessions, store, pdf)
    regions = segment_document(doc, store=store)

    assert all(isinstance(r, ConceptRegion) for r in regions)
    # Pages: 1 cover, 2 contents, 3-5 concepts, 6 appendix.
    assert [r.page for r in regions] == [3, 4, 5]
    assert [r.number_hint for r in regions] == ["1", "2a", "3"]
    for r in regions:
        x0, y0, x1, y1 = r.bbox
        assert 0 <= x0 < x1 <= A4[0], r
        assert 0 <= y0 < y1 <= A4[1], r


def test_segmentation_is_deterministic(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.segment import segment_document

    (doc,) = _fetch(sessions, store, make_pdf(berlin_pages(["1", "2"])))
    assert segment_document(doc, store=store) == segment_document(doc, store=store)


def test_records_from_two_editions_never_mixed(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    # Review Focus 1: after a new edition, each edition keeps its own bytes and its own
    # concepts; segmenting the old edition never sees the new PDF, and the reverse.
    from mkc.extraction.segment import segment_document

    v1 = make_pdf(berlin_pages(["1", "2", "3"]))
    v2 = make_pdf(berlin_pages(["1", "2", "3", "4"]))
    old, new = _fetch(sessions, store, v1, v2)

    assert old.sha256 != new.sha256
    assert store.get(PREFIX + old.sha256) == v1
    assert store.get(PREFIX + new.sha256) == v2
    assert [r.number_hint for r in segment_document(old, store=store)] == ["1", "2", "3"]
    assert [r.number_hint for r in segment_document(new, store=store)] == ["1", "2", "3", "4"]
