"""MKC-22.2: the rules from a table's cell grid to rows (decision 77), on grids in the shapes
pdfplumber gives for the real Berlin catalogue (September 2026, pages 4 to 7), which the
synthetic `ruled_table` cannot draw: a Z1 header over six rows with `None` cells and a word
split with a hyphen, and blank rows round the LBS header.

Pinned (module `mkc.extraction.tables`): `table_rows(grid, page, kind) -> list[Row]`, one
table's rows. A table is told by its header, never by its column count: `Code der LBS`
makes an LBS table; `Messkonzept` with a power-band row (`kVA`) makes a meter-tech table. A
data row starts with a list of concept numbers (or `nicht visualisiert` in an LBS table). An
LBS row whose code cell is not 13 ASCII digits is not a row; the check digit is not judged.
"""

from typing import Any


def table_rows(grid: list[list[str | None]], page: int, kind: str) -> list[Any]:
    from mkc.extraction.tables import table_rows

    return table_rows(grid, page, kind)  # type: ignore[arg-type]


Z1 = [
    ["", "Bezugsmessung, Einspeisemessung (Z1 o. Zsv), Abgren-", None, None],
    ["Messkonzept", None, None, None],
    [None, "zungsmessung (Z3)", None, None],
    ["Nr.", None, None, None],
    [None, "bis 30 kVA", "> 30 bis 55 kVA", "> 55 kVA"],
    ["", None, None, None],
    ["1", "2RZ 60 A", "2RZ 100A", "ME (Wandler)\n∆t 15"],
    ["4.4", "ME 60 A\n∆t 15", "ME 100 A\n∆t 15", "ME (Wandler)\n∆t 15"],
]

LBS = [
    ["", "", ""],
    ["Messkonzept", "Code der LBS", "Bezeichnung nach edi@energy"],
    ["", "", ""],
    ["nicht visualisiert", "9992 00000 001 8", "Verbrauch ohne Messlokation\n(Pauschalanlagen)"],
    ["11 / 12", "9992 00000 002 6", "Verbrauch mit einer Messlokation\n(Standard)"],
    [
        "2 / 2.1 / 2.2 / 8 /\n11.1",
        "9992 00000 004 2",
        "Erzeugung ohne getrennt gemessene\nErzeugung",
    ],
    ["4.4", "9992 00000 017 9", "Prüfziffer falsch"],
    ["4.4", "9992 00000 17", "zu kurz"],
    ["4.4", "", ""],
]

DECOY = [
    ["Messtechnik", "Dreipunktbefestigung", "Steckbefestigung"],
    ["2RZ 60 A", "", "X"],
    ["ME (Wandler)\n∆t 15", "X", ""],
]


def test_the_multi_row_z1_header() -> None:
    rows = table_rows(Z1, 4, "meter_tech")
    label = "Bezugsmessung, Einspeisemessung (Z1 o. Zsv), Abgrenzungsmessung (Z3)"
    assert [(r.page, r.concepts, r.code, r.label, r.cells) for r in rows] == [
        (4, ["1"], None, label, ["2RZ 60 A", "2RZ 100A", "ME (Wandler) ∆t 15"]),
        (4, ["4.4"], None, label, ["ME 60 A ∆t 15", "ME 100 A ∆t 15", "ME (Wandler) ∆t 15"]),
    ]


def test_lbs_rows_round_blank_header_rows() -> None:
    rows = table_rows(LBS, 6, "lbs")
    assert [(r.page, r.concepts, r.code, r.label, r.cells) for r in rows] == [
        (6, [], "9992000000018", "Verbrauch ohne Messlokation (Pauschalanlagen)", []),
        (6, ["11", "12"], "9992000000026", "Verbrauch mit einer Messlokation (Standard)", []),
        (6, ["2", "2.1", "2.2", "8", "11.1"], "9992000000042",
         "Erzeugung ohne getrennt gemessene Erzeugung", []),
        (6, ["4.4"], "9992000000179", "Prüfziffer falsch", []),
    ]  # fmt: skip


def test_other_tables_and_the_other_kind_give_nothing() -> None:
    assert table_rows(DECOY, 6, "lbs") == []
    assert table_rows(DECOY, 6, "meter_tech") == []
    assert table_rows(Z1, 4, "lbs") == []
    assert table_rows(LBS, 6, "meter_tech") == []
    assert table_rows([], 1, "lbs") == []
