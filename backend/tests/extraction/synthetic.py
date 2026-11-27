"""Synthetic documents for MKC-22, in the layout of the Berlin catalogue (September 2026).

Studied on the real PDF (sha256 4e12c90f...29a18, 27.11.2026), never committed:

- The LBS table (pages 6 and 7) is ruled; its columns are `Messkonzept`, `Code der LBS`,
  `Bezeichnung nach edi@energy`. A concept cell can wrap over three lines while the code
  cell has one line, centred in the row, so the code sits level with the middle line and
  the Bezeichnung lines sit between the concept lines. Read line by line, a code meets only
  part of its concepts, and the rest land next to another row (the "rows shift" of the
  spike). The table goes on over a page break with its header repeated. Rows for codes no
  concept uses say `nicht visualisiert`.
- The meter-tech tables (pages 4 and 5) are ruled: `Messkonzept Nr.`, then one column per
  power band, under a heading that names the meters (`Erzeugungsmessung (Z2)`).
- A concept page: `<number> <title>` (the title may wrap), `Anwendung:` with bullets, one
  bullet `LBS 9992 00000 018 3 (mit gemessener Erzeugung)` per stated code, a diagram with
  labels, then footnotes `*1) ...` whose text may go on over more lines. A sidebar at
  x = 461 pt has words level with the main column's lines.
"""

from tests.extraction.conftest import Box, Text, layout_pdf, ruled_table

LBS_HEADER = [["Messkonzept"], ["Code der LBS"], ["Bezeichnung nach edi@energy"]]
LBS_WIDTHS = (98.0, 99.0, 191.0)  # as on page 7

# (page, concepts, code, Bezeichnung): what `extract_tables(pdf, "lbs")` must return.
LBS_EXPECTED = [
    (1, [], "9992000000018", "Verbrauch ohne Messlokation (Pauschalanlagen)"),
    (1, ["2", "2.1", "2.2", "8", "11.1"], "9992000000042",
     "Erzeugung ohne getrennt gemessene Erzeugung"),
    (1, ["3", "3.2", "3.3", "5", "5.1", "5.2", "6.3", "7", "7.1", "11.1"], "9992000000133",
     "Erzeugung mit getrennt gemessener Erzeugung"),
    (2, ["4.4"], "9992000000175", "Verbrauchskaskade mit ungemessenen TR (ohne Erzeugungsmessung)"),
    (2, ["4.4"], "9992000000183",
     "Verbrauchskaskade mit ungemessenem Verbrauch und gemessener Erzeugung"
     " (mit Erzeugungsmessung)"),
]  # fmt: skip


def lbs_table_pdf() -> bytes:
    """Two pages. Page 1: a decoy ruled table (`Befestigung der Messtechnik`, not an LBS or
    meter-tech table), then the LBS table; page 2: the LBS table goes on, header repeated."""
    decoy, bottom = ruled_table(
        57, 120, (127.0, 128.0, 128.0),
        [[["Messtechnik"], ["Dreipunktbefestigung"], ["Steckbefestigung"]],
         [["2RZ 60 A"], [""], ["X"]],
         [["2RZ 100 A"], ["X"], [""]]],
    )  # fmt: skip
    first, _ = ruled_table(
        57, bottom + 60, LBS_WIDTHS,
        [LBS_HEADER,
         [["nicht visualisiert"], ["9992 00000 001 8"],
          ["Verbrauch ohne Messlokation", "(Pauschalanlagen)"]],
         [["2 / 2.1 / 2.2 / 8 /", "11.1"], ["9992 00000 004 2"],
          ["Erzeugung ohne getrennt gemessene", "Erzeugung"]],
         [["3 / 3.2 / 3.3 / 5 / 5.1", "/ 5.2 / 6.3 / 7 / 7.1 /", "11.1"], ["9992 00000 013 3"],
          ["Erzeugung mit getrennt gemessener", "Erzeugung"]]],
    )  # fmt: skip
    second, _ = ruled_table(
        57, 120, LBS_WIDTHS,
        [LBS_HEADER,
         [["4.4"], ["9992 00000 017 5"],
          ["Verbrauchskaskade mit ungemessenen", "TR (ohne Erzeugungsmessung)"]],
         [["4.4"], ["9992 00000 018 3"],
          ["Verbrauchskaskade mit ungemessenem", "Verbrauch und gemessener Erzeugung",
           "(mit Erzeugungsmessung)"]]],
    )  # fmt: skip
    page1 = [
        Text(57, 90, "Befestigung der Messtechnik", 12),
        *decoy,
        Text(57, bottom + 30, "LBS Lokationsbündelstruktur", 12),
        *first,
        Text(461, 72, "Messkonzepte", 8),
        Text(461, 90, "Seite/Umfang", 8),
    ]
    return layout_pdf([page1, [*second, Text(461, 72, "Messkonzepte", 8)]])


METER_BANDS = [["Nr."], ["bis 30 kVA"], ["> 30 bis 55 kVA"], ["> 55 kVA"]]
METER_WIDTHS = (80.0, 103.0, 103.0, 103.0)

# (page, concepts, heading, cells): what `extract_tables(pdf, "meter_tech")` must return.
METER_EXPECTED = [
    (1, ["3"], "Bezugsmessung (Z1)", ["2RZ 60 A", "2RZ 100A", "ME (Wandler) dt 15"]),
    (1, ["6.1"], "Bezugsmessung (Z1)", ["ME 60 A dt 15", "ME 100 A dt 15", "ME (Wandler) dt 15"]),
    (1, ["3"], "Erzeugungsmessung (Z2)", ["2RZ 60 A", "2RZ 100A", "2RZ (Wandler)"]),
    (1, ["6.1"], "Erzeugungsmessung (Z2)", ["ohne", "ohne", "ohne"]),
]


def meter_tech_pdf() -> bytes:
    """One page with two ruled meter-tech tables (Z1, then Z2). A cell may have two lines
    (`ME 60 A` over `dt 15`); a cell's lines are joined with one space."""
    items: list[Text | Box] = []
    top = 120.0
    for heading, rows in (
        ("Bezugsmessung (Z1)", [
            [["3"], ["2RZ 60 A"], ["2RZ 100A"], ["ME (Wandler)", "dt 15"]],
            [["6.1"], ["ME 60 A", "dt 15"], ["ME 100 A", "dt 15"], ["ME (Wandler)", "dt 15"]],
        ]),
        ("Erzeugungsmessung (Z2)", [
            [["3"], ["2RZ 60 A"], ["2RZ 100A"], ["2RZ (Wandler)"]],
            [["6.1"], ["ohne"], ["ohne"], ["ohne"]],
        ]),
    ):  # fmt: skip
        head, below = ruled_table(57, top, (80.0, 309.0), [[["Messkonzept"], [heading]]])
        table, top = ruled_table(57, below, METER_WIDTHS, [METER_BANDS, *rows])
        items += [*head, *table]
        top += 40
    items.append(Text(461, 72, "Messkonzepte", 8))
    return layout_pdf([items])


# Concept 4.4 in the real layout. The sidebar words sit level with main-column lines: a
# tool that reads past the region's right edge gets `PV-Anlagen Ausgabe` or a code line
# ending in `Zuständig`.
CONCEPT_LINES = [
    (72, "4.4 Überschusseinspeisung mit Erzeugungsmessung", "Messkonzepte"),
    (86, "und Abgrenzungsmessung", None),
    (110, "Anwendung:", "Seite/Umfang"),
    (124, "• PV-Anlagen", "Ausgabe"),
    (138, "• KWK-Anlagen", None),
    (152, "• steuerbare Verbrauchseinrichtungen nach § 14a EnWG (z. B. Wärmepumpe)", None),
    (166, "• LBS 9992 00000 018 3 (mit gemessener Erzeugung)", "Zuständig"),
    (180, "• LBS 9992 00000 017 5 (ohne gemessene Erzeugung)", None),
    (300, "Verteilungsnetz", None),
    (330, "Z 1", None),
    (360, "Z 3", None),
    (390, "Z 2", None),
    (400, "*1", None),
    (420, "G", None),
    (700, "*1) Der Anschluss von weiteren Erzeugungsanlagen ist parallel möglich bei:", None),
    (714, "- Anlagenzusammenfassungen nach KWKG", None),
    (728, "*2) Bei KWK-Anlagen kann i. d. R. auf Wechselrichter verzichtet werden", None),
]
CONCEPT_BBOX = (60.0, 60.0, 455.0, 760.0)  # the main column, left of the sidebar

TITLE = "Überschusseinspeisung mit Erzeugungsmessung und Abgrenzungsmessung"
APPLICATIONS = [
    "PV-Anlagen",
    "KWK-Anlagen",
    "steuerbare Verbrauchseinrichtungen nach § 14a EnWG (z. B. Wärmepumpe)",
]
FOOTNOTES = [
    "*1) Der Anschluss von weiteren Erzeugungsanlagen ist parallel möglich bei:"
    " - Anlagenzusammenfassungen nach KWKG",
    "*2) Bei KWK-Anlagen kann i. d. R. auf Wechselrichter verzichtet werden",
]
STATED = [
    ("9992000000183", "mit gemessener Erzeugung"),
    ("9992000000175", "ohne gemessene Erzeugung"),
]


def concept_page_pdf() -> bytes:
    """Page 1: concept 4.4 with two stated codes and conditions. Page 2: concept 3 with one
    stated code and no condition (`• LBS 9992 00000 013 3`)."""
    first: list[Text | Box] = []
    for top, main, side in CONCEPT_LINES:
        first.append(Text(72, top, main, 10))
        if side:
            first.append(Text(461, top, side, 8))
    first.append(Box(150, 290, 400, 440))  # the diagram's frame
    second = [
        Text(72, 72, "3 Überschusseinspeisung mit Erzeugungsmessung", 10),
        Text(461, 72, "Messkonzepte", 8),
        Text(72, 96, "Anwendung:", 10),
        Text(72, 110, "• PV-Anlagen", 10),
        Text(72, 124, "• LBS 9992 00000 013 3", 10),
        Text(461, 124, "Zuständig", 8),
        Text(72, 700, "*1) Der Anschluss von weiteren Erzeugungsanlagen ist parallel möglich.", 10),
    ]
    return layout_pdf([first, second])
