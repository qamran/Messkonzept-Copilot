"""MKC-22 mutation pass (test agent): the grid rules of `mkc.extraction.tables.table_rows` and
the line joining of `mkc.extraction.cleantext`, on hand-made cell grids (no PDF needed).

`table_rows(grid, page, kind)` takes pdfplumber's `Table.extract()` grid (a list of rows,
each a list of cell strings or None, wrapped lines separated by `"\\n"`).
"""

from mkc.extraction.cleantext import clean, join_lines
from mkc.extraction.tables import table_rows

HEAD = ["Messkonzept", "Code der LBS", "Bezeichnung nach edi@energy"]
BANDS = ["Nr.", "bis 30 kVA", "> 30 bis 55 kVA", "> 55 kVA"]


def _lbs(*rows: list[str | None], head: list[str | None] = HEAD) -> list[tuple[object, ...]]:
    return [(r.concepts, r.code, r.label) for r in table_rows([head, *rows], 6, "lbs")]


def test_nicht_visualisiert_in_any_case() -> None:
    assert _lbs(["Nicht visualisiert", "9992 00000 001 8", "Pauschal"]) == [
        ([], "9992000000018", "Pauschal")
    ]


def test_a_trailing_slash_leaves_no_empty_concept() -> None:
    assert _lbs(["4 / 4.1 /", "9992 00000 015 9", "Kaskade"]) == [
        (["4", "4.1"], "9992000000159", "Kaskade")
    ]


def test_every_part_must_be_a_concept_number() -> None:
    assert _lbs(["3 / Anlage", "9992 00000 013 3", "x"]) == []


def test_a_letter_suffix_is_part_of_the_number() -> None:
    assert _lbs(["2a", "9992 00000 004 2", "x"]) == [(["2a"], "9992000000042", "x")]


def test_a_year_is_no_concept_number() -> None:
    assert _lbs(["2026", "9992 00000 004 2", "x"]) == []


def test_only_the_exact_header_makes_an_lbs_table() -> None:
    row = ["3", "9992 00000 013 3", "x"]
    assert _lbs(row, head=["Messkonzept", "Zaehlercode", "Bezeichnung"]) == []
    assert _lbs(row, head=["Messkonzept", "Codeliste", "Bezeichnung"]) == []


def test_a_code_of_twelve_digits_is_skipped() -> None:
    assert _lbs(["3", "9992 00000 013", "x"]) == []


def test_a_row_after_the_first_that_is_no_concept_list_is_skipped() -> None:
    assert _lbs(
        ["3", "9992 00000 013 3", "x"],
        ["", "9992 00000 004 2", "y"],
        ["Summe", "9992 00000 004 2", "z"],
    ) == [(["3"], "9992000000133", "x")]  # fmt: skip


def test_an_empty_grid_row_is_no_error() -> None:
    assert _lbs([], ["3", "9992 00000 013 3", "x"]) == [(["3"], "9992000000133", "x")]


def test_a_word_split_inside_a_cell_is_joined() -> None:
    assert _lbs(["3", "9992 00000 013 3", "Erzeugungs-\nmessung"]) == [
        (["3"], "9992000000133", "Erzeugungsmessung")
    ]


def test_a_meter_table_needs_messkonzept_in_its_first_column() -> None:
    grid = [["Leistung", "Z2", None, None], ["Anlage", *BANDS[1:]],
            ["3", "2RZ 60 A", "2RZ 100A", "2RZ (Wandler)"]]  # fmt: skip
    assert table_rows(grid, 4, "meter_tech") == []


def test_a_meter_table_skips_a_row_with_no_concept() -> None:
    grid = [["Messkonzept", "Erzeugungsmessung (Z2)", None, None], BANDS,
            ["3", "ohne", "ohne", "ohne"],
            ["nicht visualisiert", "ohne", "ohne", "ohne"]]  # fmt: skip
    rows = table_rows(grid, 4, "meter_tech")
    assert [(r.concepts, r.label, r.cells) for r in rows] == [
        (["3"], "Erzeugungsmessung (Z2)", ["ohne", "ohne", "ohne"])
    ]


def test_clean_makes_every_white_space_run_one_space() -> None:
    assert clean(" a\tb\n\n c ") == "a b c"


def test_join_lines_keeps_the_hyphen_before_a_capital() -> None:
    assert join_lines(["Waermepumpen-", "Anlage"]) == "Waermepumpen- Anlage"


def test_join_lines_joins_after_a_sharp_s() -> None:
    assert join_lines(["groß-", "flächig"]) == "großflächig"


def test_join_lines_keeps_the_hyphen_before_sowie() -> None:
    assert join_lines(["Bezugs-", "sowie Einspeisemessung"]) == "Bezugs- sowie Einspeisemessung"
