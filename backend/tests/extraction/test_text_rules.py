"""MKC-22.1: the `extract_text` rules the acceptance tests leave open (decision 76).

- A printed code with a wrong check digit is kept as printed: it is what the operator stated.
  Extraction does not judge it; `validate_draft` (MKC-28) flags it.
- A bullet that wraps goes on in a line indented past the bullet sign; it is joined with one
  space, also an `LBS` bullet whose condition wraps.
- A code is 13 ASCII digits; a superscript or other Unicode digit after it is not part of it.
- A wrapped title line that ends in a hyphen before a lowercase word is joined without it.
"""

from typing import Any

from tests.extraction.conftest import Text, layout_pdf


def _fields(lines: list[Text]) -> Any:
    from mkc.extraction.segment import ConceptRegion
    from mkc.extraction.text import extract_text

    pdf = layout_pdf([lines])
    region = ConceptRegion(page=1, bbox=(60.0, 60.0, 455.0, 760.0), number_hint=None)
    return extract_text(pdf, region)


def test_a_code_with_a_wrong_check_digit_is_kept_as_printed() -> None:
    fields = _fields(
        [Text(72, 72, "1 Volleinspeisung", 10), Text(72, 96, "Anwendung:", 10),
         Text(72, 110, "• LBS 9992 00000 003 5 (falsche Prüfziffer)", 10)]
    )  # fmt: skip
    assert [(s.code, s.condition) for s in fields.stated_lbs] == [
        ("9992000000035", "falsche Prüfziffer")
    ]


def test_a_wrapped_bullet_and_a_wrapped_condition_are_joined() -> None:
    fields = _fields(
        [Text(72, 72, "1 Volleinspeisung", 10), Text(72, 96, "Anwendung:", 10),
         Text(72, 110, "• steuerbare Verbrauchseinrichtungen", 10),
         Text(78, 124, "nach § 14a EnWG", 10),
         Text(72, 138, "• LBS 9992 00000 018 3 (mit gemessener", 10),
         Text(78, 152, "Erzeugung)", 10)]
    )  # fmt: skip
    assert fields.applications == ["steuerbare Verbrauchseinrichtungen nach § 14a EnWG"]
    assert [(s.code, s.condition) for s in fields.stated_lbs] == [
        ("9992000000183", "mit gemessener Erzeugung")
    ]


def test_a_unicode_digit_after_a_code_is_not_part_of_it() -> None:
    fields = _fields(
        [Text(72, 72, "1 Volleinspeisung", 10), Text(72, 96, "Anwendung:", 10),
         Text(72, 110, "• LBS 9992 00000 013 3²", 10)]
    )  # fmt: skip
    assert [s.code for s in fields.stated_lbs] == ["9992000000133"]


def test_a_hyphenated_title_is_joined() -> None:
    fields = _fields(
        [Text(72, 72, "4.4 Überschusseinspeisung mit Abgren-", 14),
         Text(100, 88, "zungsmessung", 14), Text(72, 110, "Anwendung:", 10),
         Text(72, 124, "• PV-Anlagen", 10)]
    )  # fmt: skip
    assert fields.title == "Überschusseinspeisung mit Abgrenzungsmessung"
    assert fields.applications == ["PV-Anlagen"]


def test_a_marker_at_the_end_of_a_line_starts_the_next_footnote() -> None:
    """Berlin page 22 (concept 5.1) prints `*2)` at the end of the line before its text."""
    fields = _fields(
        [Text(72, 72, "5.1 Überschusseinspeisung", 10),
         Text(72, 700, "*1) Der Anschluss ist parallel möglich bei:", 10),
         Text(72, 714, "- Parallelbetrieb von PV-Anlagen *2)", 10),
         Text(72, 728, "Der Anschluss von Speichern ist auch im Verbrauchspfad möglich", 10)]
    )  # fmt: skip
    assert fields.footnotes == [
        "*1) Der Anschluss ist parallel möglich bei: - Parallelbetrieb von PV-Anlagen",
        "*2) Der Anschluss von Speichern ist auch im Verbrauchspfad möglich",
    ]
