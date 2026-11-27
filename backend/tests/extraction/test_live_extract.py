"""MKC-22 live test: on the real Berlin catalogue, the LBS table and the codes stated on the
concept pages of 3, 4.4 and 11.1 agree (the spike facts of 24.11.2026).

Deselected by default (`-m 'not live'`). Run on purpose, with the coordinator's go, by
`uv run pytest -m live tests/extraction/test_live_extract.py`. It fetches the PDF from the
allow-listed URL with the real `http_get`; the bytes go only to the in-memory store. No model
calls.
"""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.extraction.conftest import MemoryStore

# Read by the test agent on 27.11.2026 from the September 2026 edition (sha256
# 4e12c90faeb35383dafe86f9ae55ddad220dea50d827167f009d22fe27b29a18): the stated codes on the
# concept pages (3: page 14; 4.4: page 20; 11.1: page 32) and the rows of the LBS table
# (pages 6 and 7) that list each concept. Both sources give the same codes.
BERLIN_SHA256 = "4e12c90faeb35383dafe86f9ae55ddad220dea50d827167f009d22fe27b29a18"
EXPECTED_BERLIN_LBS: dict[str, set[str]] | None = {
    "3": {"9992000000133"},
    "4.4": {"9992000000175", "9992000000183"},
    "11.1": {"9992000000042", "9992000000133"},
}
# The Z2 (Erzeugungsmessung) row of concept 3 on page 4, one cell per power band.
EXPECTED_BERLIN_Z2_CONCEPT_3 = ["2RZ 60 A", "2RZ 100A", "2RZ (Wandler)"]


@pytest.mark.live
def test_berlin_lbs_table_matches_the_stated_codes(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document, http_get
    from mkc.extraction.segment import segment_document
    from mkc.extraction.tables import extract_tables
    from mkc.extraction.text import extract_text

    doc = fetch_document("stromnetz-berlin", sessions=sessions, store=store, get=http_get)
    if doc.sha256 != BERLIN_SHA256:
        pytest.skip(f"a new Berlin edition ({doc.sha256}): read its codes again by hand")
    assert EXPECTED_BERLIN_LBS is not None
    pdf = store.get(doc.ref)
    rows = extract_tables(pdf, "lbs")
    assert {r.page for r in rows} == {6, 7}
    regions = {r.number_hint: r for r in segment_document(doc, store=store)}
    for concept, codes in EXPECTED_BERLIN_LBS.items():
        in_table = {r.code for r in rows if concept in r.concepts}
        assert in_table == codes, f"table, concept {concept}"
        stated = {s.code for s in extract_text(pdf, regions[concept]).stated_lbs}
        assert stated == codes, f"stated on the concept page, concept {concept}"


@pytest.mark.live
def test_berlin_meter_tech_row_of_concept_3(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document, http_get
    from mkc.extraction.tables import extract_tables

    doc = fetch_document("stromnetz-berlin", sessions=sessions, store=store, get=http_get)
    if doc.sha256 != BERLIN_SHA256:
        pytest.skip(f"a new Berlin edition ({doc.sha256}): read its rows again by hand")
    rows = extract_tables(store.get(doc.ref), "meter_tech")
    z2 = [r for r in rows if r.concepts == ["3"] and "(Z2)" in r.label]
    assert [list(r.cells) for r in z2] == [EXPECTED_BERLIN_Z2_CONCEPT_3]
    assert {r.page for r in rows} == {4, 5}
