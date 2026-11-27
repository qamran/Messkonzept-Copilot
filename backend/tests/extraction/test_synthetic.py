"""MKC-22: the synthetic documents themselves (green before any MKC-22 code exists).

They guard the fixtures: the red tests fail on a missing module whatever the PDF holds, so
these show the PDFs carry what the red tests read: pdfplumber's raw cell grid has every
row whole, and the line-by-line text has the shift.
"""

import io

import pdfplumber

from tests.extraction.synthetic import (
    CONCEPT_BBOX,
    concept_page_pdf,
    lbs_table_pdf,
    meter_tech_pdf,
)


def _grids(pdf: bytes) -> list[list[list[str | None]]]:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return [t.extract() for page in doc.pages for t in page.find_tables()]


def test_the_lbs_pdf_has_a_decoy_and_the_table_over_two_pages() -> None:
    grids = _grids(lbs_table_pdf())
    assert [g[0] for g in grids] == [
        ["Messtechnik", "Dreipunktbefestigung", "Steckbefestigung"],
        ["Messkonzept", "Code der LBS", "Bezeichnung nach edi@energy"],
        ["Messkonzept", "Code der LBS", "Bezeichnung nach edi@energy"],
    ]
    assert grids[1][3] == [
        "3 / 3.2 / 3.3 / 5 / 5.1\n/ 5.2 / 6.3 / 7 / 7.1 /\n11.1",
        "9992 00000 013 3",
        "Erzeugung mit getrennt gemessener\nErzeugung",
    ]


def test_the_lbs_pdf_shifts_rows_line_by_line() -> None:
    with pdfplumber.open(io.BytesIO(lbs_table_pdf())) as doc:
        lines = doc.pages[0].extract_text().splitlines()
    assert "9992 00000 004 2" in lines, "the code has a line of its own"
    assert "11.1 Erzeugung" in lines, "11.1 meets the Bezeichnung's second line"


def test_the_meter_tech_pdf_has_two_tables() -> None:
    grids = _grids(meter_tech_pdf())
    assert [g[0][1] for g in grids] == ["Bezugsmessung (Z1)", "Erzeugungsmessung (Z2)"]
    assert grids[0][3] == ["6.1", "ME 60 A\ndt 15", "ME 100 A\ndt 15", "ME (Wandler)\ndt 15"]


def test_the_concept_page_has_a_sidebar_level_with_the_main_column() -> None:
    with pdfplumber.open(io.BytesIO(concept_page_pdf())) as doc:
        page = doc.pages[0]
        full = page.extract_text()
        cropped = page.crop(CONCEPT_BBOX).extract_text()
    assert "• PV-Anlagen Ausgabe" in full
    assert "Ausgabe" not in cropped and "• PV-Anlagen" in cropped
    assert "Wärmepumpe" in cropped and "§ 14a" in cropped
