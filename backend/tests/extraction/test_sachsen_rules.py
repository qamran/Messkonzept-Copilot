"""MKC-27 (test agent's mutation pass): rules of `segment_sachsen` the first acceptance tests
left open. Each test names the mutant it kills in the lane file ("Mutation pass")."""

from typing import Any

import pytest

from tests.extraction.sachsen_pdf import (
    Box,
    Curve,
    Image,
    Line,
    Text,
    half,
    make_landscape_pdf,
)


def _segment(*items: Any) -> list[Any]:
    from mkc.extraction.sachsen import segment_sachsen

    return segment_sachsen(make_landscape_pdf([list(items)]))


def test_heading_words_a_little_off_the_baseline_are_still_one_line() -> None:
    # The number sits 2 pt lower than `Messkonzept` (a superscript-like offset).
    items = [Text(11, 28, "Messkonzept", 10), Text(73, 30, "2-1:", 10), Text(11, 42, "Titel")]
    (region,) = _segment(*items)
    assert region.number_hint == "2-1"


def test_a_heading_word_alone_on_its_line_is_not_a_heading() -> None:
    assert _segment(Text(11, 28, "Messkonzept", 10), Text(11, 42, "2-1:", 10)) == []


@pytest.mark.parametrize("word", ["2.1:", "2-1:00", "A-1:", "2-1"])
def test_only_sachsen_numbers_with_a_colon_are_headings(word: str) -> None:
    assert (
        _segment(Text(11, 28, "Messkonzept", 10), Text(73, 28, word, 10), Text(11, 42, "T")) == []
    )


@pytest.mark.parametrize("title", ["Nr (tbd)", "NR. (TBD)", "Nr.  (tbd)"])
def test_placeholder_titles_are_matched_loosely(title: str) -> None:
    assert _segment(*half(11.0, "13", title, figure=False)) == []


def test_a_placeholder_whose_title_is_the_only_other_line() -> None:
    items = [Text(11, 28, "Messkonzept 13:", 10), Text(11, 42, "Nr. (tbd)", 10)]
    assert _segment(*items) == []


def test_a_title_that_only_contains_tbd_is_a_concept() -> None:
    (region,) = _segment(*half(11.0, "3-1", "Anlage Nr. (tbd) mit Speicher"))
    assert region.number_hint == "3-1"


def test_frame_lines_above_the_heading_are_left_out() -> None:
    # The real frame starts at 21 pt, the heading at 28 pt: the region starts at the heading.
    (region,) = _segment(*half(11.0, "2-1", "T"), Box(4, 21, 470, 483))
    assert region.bbox[1] > 25


def test_the_divider_that_crosses_the_middle_is_not_part_of_either_half() -> None:
    left, right = _segment(
        *half(11.0, "2-1", "T"), *half(499.0, "2-1a", "T"), Box(474, 40, 491, 480)
    )
    assert left.bbox[2] <= 480 and right.bbox[0] > 490


def test_a_figure_ending_just_inside_the_middle_belongs_to_the_left_half() -> None:
    (left,) = _segment(*half(11.0, "2-1", "T"), Box(300, 100, 479.8, 300))
    assert left.bbox[2] == 479.8


def test_bbox_values_are_rounded_to_two_decimals() -> None:
    (region,) = _segment(*half(11.37, "2-1", "T"))
    assert region.bbox[0] == 11.37


@pytest.mark.parametrize("figure", [Line(20, 60, 30, 470), Curve(100, 60, 300, 468)])
def test_lines_and_curves_count_as_content(figure: Any) -> None:
    (region,) = _segment(*half(11.0, "2-1", "T"), figure)
    assert region.bbox[3] >= 468


def test_an_image_counts_as_content() -> None:
    (region,) = _segment(*half(11.0, "2-1", "T"), Image(320, 60, 420, 469))
    assert region.bbox[3] >= 468 and region.bbox[2] >= 420
