"""MKC-22 mutation pass (test agent): the line rules of the naive E1 baseline
(`mkc.extraction.naive`), one synthetic line each.

- A line with a code is an LBS row only when all text before the code is concept numbers
  or `nicht visualisiert`; the rest of the line is the label.
- A code is 13 digits not glued to a longer digit run.
- A meter row keeps the rest of its line as one cell, under the page's `(Zn)` heading.
- `naive_text` holds no control character, also when a font maps a glyph to U+0000.
"""

from mkc.extraction.naive import naive_tables, naive_text
from tests.extraction.conftest import Text, layout_pdf


def test_lbs_lines() -> None:
    pdf = layout_pdf(
        [[Text(57, 100, "nicht visualisiert 9992 00000 001 8 Verbrauch ohne Messlokation"),
          Text(57, 130, "Stand 9992 00000 003 4"),
          Text(57, 160, "1 99992 00000 003 4 Erzeugung")]]
    )  # fmt: skip
    rows = naive_tables(pdf, "lbs")
    assert [(r.concepts, r.code, r.label) for r in rows] == [
        ([], "9992000000018", "Verbrauch ohne Messlokation")
    ]


def test_a_meter_row_is_one_cell_under_its_heading() -> None:
    pdf = layout_pdf(
        [[Text(57, 100, "Messkonzept Erzeugungsmessung (Z2)"),
          Text(57, 130, "3 2RZ 60 A 2RZ 100A")]]
    )  # fmt: skip
    rows = naive_tables(pdf, "meter_tech")
    assert [(r.concepts, r.label, r.cells) for r in rows] == [
        (["3"], "Messkonzept Erzeugungsmessung (Z2)", ["2RZ 60 A 2RZ 100A"])
    ]


def test_naive_text_has_no_nul() -> None:
    pdf = layout_pdf([[Text(57, 100, "PV-Anlagen #")]], nul_for="#")
    assert chr(0) not in naive_text(pdf)
    assert "PV-Anlagen" in naive_text(pdf)
