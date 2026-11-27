"""MKC-22: `extract_tables` (feature 30) and the naive text baseline kept for E1.

Pinned interface (module `mkc.extraction.tables`):

    extract_tables(pdf: bytes, kind: Literal["meter_tech", "lbs"]) -> list[Row]

`Row` is a frozen Pydantic model:

- `kind`: the table kind asked for.
- `page`: 1-based page of the row (for citations).
- `concepts`: the concept numbers in the row's first cell, as printed, in order (`11.1`,
  `2a`); `[]` for `nicht visualisiert`.
- `code`: `lbs`: the 13-digit LBS code with the spaces removed; `meter_tech`: None.
- `label`: `lbs`: the Bezeichnung; `meter_tech`: the table's heading (`Erzeugungsmessung (Z2)`).
- `cells`: `meter_tech`: one entry per power band, left to right; `lbs`: `[]`.

Text that wraps inside a cell is joined with one space. Header rows are not rows. A table
that goes on over a page break comes back as one list, in page order. Other ruled tables
(`Befestigung der Messtechnik`) and unruled lines that look like rows give nothing.

Baseline (module `mkc.extraction.naive`), pure Python, no system binary:

    naive_text(pdf: bytes) -> str          # pdftotext-style: every page's text in reading
                                           # order, pages separated by form feeds ("\f")
    naive_tables(pdf: bytes, kind) -> list[Row]   # the same rows, read line by line from
                                                  # naive_text, with no cell grid
"""

from typing import Any

from tests.extraction.conftest import berlin_pages, make_pdf
from tests.extraction.synthetic import (
    LBS_EXPECTED,
    METER_EXPECTED,
    lbs_table_pdf,
    meter_tech_pdf,
)


def _lbs(rows: list[Any]) -> list[tuple[Any, ...]]:
    return [(r.page, list(r.concepts), r.code, r.label) for r in rows]


def test_pdfplumber_rows_correct() -> None:
    """The ruled LBS table: every code keeps all its concepts and its own Bezeichnung, also
    where the cells wrap, and the table goes on over the page break."""
    from mkc.extraction.tables import extract_tables

    rows = extract_tables(lbs_table_pdf(), "lbs")
    assert _lbs(rows) == LBS_EXPECTED
    assert {r.kind for r in rows} == {"lbs"}
    assert all(list(r.cells) == [] for r in rows)


def test_naive_text_shifts_the_rows() -> None:
    """The same table read line by line: the code `9992 00000 013 3` sits level with the
    middle of its three concept lines, so `3` above it and `11.1` below it are not on its
    line, and the lines of other rows' text lie between. This is the spike's failure."""
    from mkc.extraction.naive import naive_text

    text = naive_text(lbs_table_pdf())
    assert text.count("\f") == 1, "two pages, one form feed between them"
    code_lines = [line for line in text.splitlines() if "9992 00000 013 3" in line]
    assert len(code_lines) == 1
    assert "3 / 3.2" not in code_lines[0]
    assert "11.1" not in code_lines[0]


def test_naive_baseline_gets_a_row_wrong() -> None:
    """`naive_tables` is the E1 baseline: it returns rows of the same shape, but at least
    the wrapped row of `9992000000133` does not get its true concepts."""
    from mkc.extraction.naive import naive_tables

    naive = naive_tables(lbs_table_pdf(), "lbs")
    truth = {code: concepts for _, concepts, code, _ in LBS_EXPECTED}
    got = {r.code: list(r.concepts) for r in naive}
    assert "9992000000133" in got, "the baseline finds the code, but pairs it wrongly"
    assert got["9992000000133"] != truth["9992000000133"]
    assert _lbs(naive) != LBS_EXPECTED


def test_naive_text_reads_every_page() -> None:
    from mkc.extraction.naive import naive_text

    text = naive_text(make_pdf(berlin_pages(["1", "2a"])))
    pages = text.split("\f")
    assert len(pages) >= 5
    assert "2a Ueberschusseinspeisung" in pages[3]


def test_meter_tech_rows_correct() -> None:
    """Both meter-tech tables, Z1 then Z2: one row per concept and table, the heading kept,
    one cell per power band; a cell's two lines (`ME 60 A` over `dt 15`) are joined."""
    from mkc.extraction.tables import extract_tables

    rows = extract_tables(meter_tech_pdf(), "meter_tech")
    got = [(r.page, list(r.concepts), r.label, list(r.cells)) for r in rows]
    assert got == METER_EXPECTED
    assert {r.kind for r in rows} == {"meter_tech"}
    assert all(r.code is None for r in rows)


def test_the_kinds_do_not_mix() -> None:
    from mkc.extraction.tables import extract_tables

    assert extract_tables(meter_tech_pdf(), "lbs") == []
    assert extract_tables(lbs_table_pdf(), "meter_tech") == []


def test_a_document_without_tables_gives_no_rows() -> None:
    """The Berlin-style concept pages and the unruled appendix lines (`1 2RZ 60 A ...`) are
    no table; SachsenNetze has no LBS table at all."""
    from mkc.extraction.tables import extract_tables

    pdf = make_pdf(berlin_pages(["1", "2a", "3"]))
    assert extract_tables(pdf, "lbs") == []
    assert extract_tables(pdf, "meter_tech") == []


def test_extract_tables_is_deterministic() -> None:
    from mkc.extraction.tables import extract_tables

    pdf = lbs_table_pdf()
    first = extract_tables(pdf, "lbs")
    assert extract_tables(pdf, "lbs") == first
    assert extract_tables(lbs_table_pdf(), "lbs") == first
    assert [r.model_dump(mode="json") for r in first] == [
        r.model_dump(mode="json") for r in extract_tables(pdf, "lbs")
    ]
