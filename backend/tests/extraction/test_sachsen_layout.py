"""MKC-27.1: the real SachsenNetze page furniture does not leak into a region.

The acceptance fixture has no frames. The real pages (09/2025 edition, page 3 studied on
27.11.2026) also carry: a page background (0, 0, 960, 540), a divider box between the halves
(474.3 to 491.3, across the middle at 480), frame lines that start above the heading
(y = 20.3), a page-wide rule at y = 483.2 and, in the right half, a logo from y = 498 to 527.
The frames themselves end at y = 482.8; the footer text starts at y = 509.
"""

from typing import Any

from tests.extraction.sachsen_pdf import (
    HEIGHT,
    LEFT_X,
    RIGHT_X,
    WIDTH,
    Box,
    Text,
    footer,
    half,
    make_landscape_pdf,
)

MID = WIDTH / 2


def _furniture() -> list[Any]:
    return [
        Box(0, 0, WIDTH, HEIGHT),  # page background
        Box(474.3, 20.8, 491.3, 482.8),  # divider between the halves
        Box(3.7, 20.3, 474.3, 71.2),  # left heading frame, above the heading
        Box(491.3, 20.3, 956.3, 71.2),  # right heading frame
        Box(3.7, 424.0, 474.3, 482.8),  # left bottom frame
        Box(491.3, 424.0, 956.3, 482.8),  # right bottom frame
        Box(0, 483.0, WIDTH, 483.4),  # page-wide rule
        Box(833.4, 498.0, 932.1, 526.7),  # logo in the right half, below the frames
    ]


def _page_regions() -> list[Any]:
    from mkc.extraction.sachsen import segment_sachsen

    page = [
        *_furniture(),
        *half(LEFT_X, "2-1", "Volleinspeisung"),
        *half(RIGHT_X, "2-1a", "Volleinspeisung mit Erzeugungsmessung"),
        *footer(3),
    ]
    return segment_sachsen(make_landscape_pdf([page]))


def test_page_furniture_stays_out_of_the_regions() -> None:
    left, right = _page_regions()
    assert (left.number_hint, right.number_hint) == ("2-1", "2-1a")
    assert 3 <= left.bbox[0] < 12 and left.bbox[2] <= 475, "background and divider left out"
    assert 491 <= right.bbox[0] < 500 and right.bbox[2] <= 957
    for r in (left, right):
        assert 20 <= r.bbox[1] <= 35, "starts at the heading, not at the frame above it"
        assert 482 <= r.bbox[3] < 490, "ends at the bottom frame, above the rule's gap and logo"


def test_a_heading_needs_the_number_and_its_colon() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    pdf = make_landscape_pdf(
        [
            [
                Text(LEFT_X, 28, "Messkonzept 2-1", 10),  # no colon
                Text(LEFT_X, 42, "Volleinspeisung", 10),
                Text(RIGHT_X, 28, "Messkonzepte 2-1a:", 10),  # another word
                Text(RIGHT_X, 42, "Volleinspeisung", 10),
            ],
            [
                Text(LEFT_X, 28, "Messkonzept 2025:", 10),  # a year, not a number
                Text(LEFT_X, 42, "Volleinspeisung", 10),
                Text(RIGHT_X, 28, "Messkonzept 3-2b: Steuerbare", 10),  # heading and more
                Text(RIGHT_X, 42, "Verbrauchseinrichtung", 10),
            ],
        ]
    )
    assert [(r.page, r.number_hint) for r in segment_sachsen(pdf)] == [(2, "3-2b")]


def test_a_placeholder_is_known_by_its_title_not_by_a_missing_figure() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    pdf = make_landscape_pdf(
        [
            [
                *_furniture(),
                *half(LEFT_X, "3-5", "Steuerbare Verbrauchseinrichtung", figure=False),
                *half(RIGHT_X, "13", "Nr. (tbd)"),  # frames and a figure, still a placeholder
            ]
        ]
    )
    assert [r.number_hint for r in segment_sachsen(pdf)] == ["3-5"]


def test_a_title_that_only_mentions_tbd_is_a_concept() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    pdf = make_landscape_pdf([half(LEFT_X, "3-1", "Eigenverbrauch (tbd Speicher)")])
    assert [r.number_hint for r in segment_sachsen(pdf)] == ["3-1"]


def test_regions_follow_the_middle_of_any_page_width() -> None:
    from mkc.extraction.sachsen import segment_sachsen

    width = 842.0  # A4 landscape
    pdf = make_landscape_pdf(
        [[*half(11.0, "2-2", "Ueberschuss"), *half(432.0, "2-2a", "Speicher")]],
        size=(width, 595.0),
    )
    left, right = segment_sachsen(pdf)
    assert left.bbox[2] <= width / 2 <= right.bbox[0]
    assert right.bbox[2] <= width
