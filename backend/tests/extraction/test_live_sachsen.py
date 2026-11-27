"""MKC-27 live test: the real SachsenNetze catalogue yields 11 concepts.

Deselected by default. Run on purpose, with the coordinator's go, by
`uv run pytest -m live tests/extraction/test_live_sachsen.py`. The bytes go only to the
in-memory store, never to disk or the repo.

Real catalogue (checked by hand 27.11.2026, 09/2025 edition, 9 pages, 960 x 540 pt): pages 3 to
8 hold 12 halves, 11 numbered concepts (2-1, 2-1a, 2-2, 2-2a, 2-3, 2-3a, 2-3b, 2-5a, 3-1, 3-2,
3-5) and one placeholder (`13`, `Nr. (tbd)`, page 8 right) that is not a concept.
"""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.extraction.conftest import MemoryStore

EXPECTED_HINTS = ["2-1", "2-1a", "2-2", "2-2a", "2-3", "2-3a", "2-3b", "2-5a", "3-1", "3-2", "3-5"]
EXPECTED_PAGES = [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8]


@pytest.mark.live
def test_sachsennetze_yields_11_concepts(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document, http_get
    from mkc.extraction.segment import segment_document

    doc = fetch_document("sachsennetze", sessions=sessions, store=store, get=http_get)
    regions = segment_document(doc, store=store)
    assert len(regions) == 11
    assert [r.number_hint for r in regions] == EXPECTED_HINTS
    assert [r.page for r in regions] == EXPECTED_PAGES
