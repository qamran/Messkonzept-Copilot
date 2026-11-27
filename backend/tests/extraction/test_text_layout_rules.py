"""MKC-22 mutation pass (test agent): the layout rules of `extract_text` that the first tests
left open. Each test pins one rule of `mkc.extraction.text` with a small synthetic page.

- A wrapped line goes on only at a line's pitch (at most 1.6 type sizes below): a line
  further down does not join a bullet or a footnote, nor does a line that is not indented
  past the bullet sign or that starts left of the footnote marker.
- The title stops at `Anwendung:` and at a line in another type size.
- Only the bullets of the list right after `Anwendung:` are applications.
- A stated code is exactly 13 digits: a 14th digit makes it no code.
- A bbox with a value that is no number, and a page past the end, are `ValueError`s.
"""

import math
from typing import Any

import pytest

from mkc.extraction.segment import ConceptRegion
from tests.extraction.conftest import Text, layout_pdf

PAGE = (0.0, 0.0, 595.0, 842.0)


def _fields(*lines: tuple[float, float, str, float]) -> Any:
    from mkc.extraction.text import extract_text

    pdf = layout_pdf([[Text(x, top, text, size) for x, top, text, size in lines]])
    return extract_text(pdf, ConceptRegion(page=1, bbox=PAGE, number_hint="1"))


HEAD = (72, 72, "1 Volleinspeisung", 10)


def test_the_title_stops_at_anwendung_also_one_pitch_below() -> None:
    f = _fields(HEAD, (72, 86, "Anwendung:", 10), (72, 100, "• PV-Anlagen", 10))
    assert f.title == "Volleinspeisung"
    assert f.applications == ["PV-Anlagen"]


def test_the_title_stops_at_a_line_in_another_type_size() -> None:
    f = _fields(
        (72, 72, "1 Volleinspeisung", 14), (72, 92, "mit Speicher", 10),
        (72, 130, "Anwendung:", 10),
    )  # fmt: skip
    assert f.title == "Volleinspeisung"


def test_only_the_list_after_anwendung_holds_applications() -> None:
    f = _fields(
        HEAD, (72, 100, "Anwendung:", 10), (72, 114, "• PV-Anlagen", 10),
        (72, 300, "Hinweis:", 10), (72, 314, "• Zaehler im Keller", 10),
    )  # fmt: skip
    assert f.applications == ["PV-Anlagen"]


def test_a_line_not_indented_past_the_bullet_is_not_part_of_it() -> None:
    f = _fields(
        HEAD, (72, 100, "Anwendung:", 10), (72, 114, "• PV-Anlagen", 10),
        (72, 128, "Verteilungsnetz", 10),
    )  # fmt: skip
    assert f.applications == ["PV-Anlagen"]


def test_an_indented_line_far_below_is_not_part_of_the_bullet() -> None:
    f = _fields(
        HEAD, (72, 100, "Anwendung:", 10), (72, 114, "• PV-Anlagen", 10),
        (82, 200, "Steuereinheit", 10),
    )  # fmt: skip
    assert f.applications == ["PV-Anlagen"]


def test_a_line_left_of_the_marker_is_not_part_of_the_footnote() -> None:
    f = _fields(HEAD, (100, 700, "*1) Fussnote", 10), (72, 714, "Seite drei", 10))
    assert f.footnotes == ["*1) Fussnote"]


@pytest.mark.parametrize("gap", [25, 80])
def test_a_line_beyond_the_pitch_is_not_part_of_the_footnote(gap: float) -> None:
    f = _fields(HEAD, (72, 700, "*1) Fussnote", 10), (72, 700 + gap, "Stand 2026", 10))
    assert f.footnotes == ["*1) Fussnote"]


def test_a_fourteenth_digit_makes_it_no_code() -> None:
    f = _fields(HEAD, (72, 100, "• LBS 99920000001334", 10))
    assert f.stated_lbs == []


def test_a_bbox_that_is_no_number_is_a_value_error() -> None:
    from mkc.extraction.text import extract_text

    pdf = layout_pdf([[Text(*HEAD)]])
    bbox = (math.nan, 0.0, 595.0, 842.0)
    with pytest.raises(ValueError):
        extract_text(pdf, ConceptRegion(page=1, bbox=bbox, number_hint="1"))


def test_a_page_past_the_end_is_a_value_error() -> None:
    from mkc.extraction.text import extract_text

    pdf = layout_pdf([[Text(*HEAD)]])
    with pytest.raises(ValueError):
        extract_text(pdf, ConceptRegion(page=2, bbox=PAGE, number_hint="1"))
