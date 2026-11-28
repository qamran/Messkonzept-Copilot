"""MKC-23 (PR #215 findings 3 and 4): pins for MKC-22 mutation survivors 9 and 11.

These pin the current behaviour (green on arrival, not red tests):

- Survivor 9 (`cleantext.py`, `_SPLIT_WORD`): only a lowercase letter before the line-end
  hyphen joins a split word. After a digit (`Z2-` / `zähler`) the hyphen and a space stay.
- Survivor 11 (`tables.py`, `_lbs_rows`): the label is the cell right of `Code der LBS`, not
  the last cell, so an LBS table with a fourth column keeps the Bezeichnung as its label.
"""

from tests.extraction.conftest import layout_pdf, ruled_table


def test_a_hyphen_after_a_digit_is_kept() -> None:
    from mkc.extraction.cleantext import join_lines

    assert join_lines(["Z2-", "zähler"]) == "Z2- zähler"
    assert join_lines(["Zweirichtungs-", "zähler"]) == "Zweirichtungszähler"


def test_an_lbs_table_with_a_fourth_column_keeps_the_bezeichnung() -> None:
    from mkc.extraction.tables import extract_tables

    table, _ = ruled_table(
        40, 120, (90.0, 99.0, 180.0, 120.0),
        [[["Messkonzept"], ["Code der LBS"], ["Bezeichnung nach edi@energy"], ["Bemerkung"]],
         [["3 / 3.2"], ["9992 00000 013 3"], ["Erzeugung mit getrennt", "gemessener Erzeugung"],
          ["siehe Anhang"]]],
    )  # fmt: skip
    (row,) = extract_tables(layout_pdf([table]), "lbs")
    assert row.code == "9992000000133"
    assert row.concepts == ["3", "3.2"]
    assert row.label == "Erzeugung mit getrennt gemessener Erzeugung"
