"""MKC-21 live test: the real Berlin catalogue yields the expected concept count.

Deselected by default (`-m 'not live'`). Run on purpose, with the coordinator's go, by
`uv run pytest -m live tests/extraction/test_live_berlin.py`. It fetches the PDF from the
allow-listed URL in `backend/data/operators.yaml` with the real `http_get`; the bytes go
only to the in-memory store, never to disk or the repo.
"""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.extraction.conftest import MemoryStore

# First live run 27.11.2026 20:51 (lane file): 26 regions on pages 8-33 of the September 2026
# edition (sha256 4e12c90f...29a18), checked by hand against the contents on page 2, which
# lists the same 26 concepts (1 to 12), one page each.
EXPECTED_BERLIN_CONCEPTS: int | None = 26


@pytest.mark.live
def test_berlin_yields_the_expected_concept_count(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document, http_get
    from mkc.extraction.segment import segment_document

    doc = fetch_document("stromnetz-berlin", sessions=sessions, store=store, get=http_get)
    regions = segment_document(doc, store=store)
    hints = [r.number_hint for r in regions]
    assert EXPECTED_BERLIN_CONCEPTS is not None, (
        f"first live run: {len(regions)} regions, hints {hints}, sha256 {doc.sha256}; "
        "verify by hand, then set EXPECTED_BERLIN_CONCEPTS"
    )
    assert len(regions) == EXPECTED_BERLIN_CONCEPTS
    assert all(h for h in hints), "every Berlin concept page has a number"
    assert len(set(hints)) == len(hints), "a concept number appears twice"
