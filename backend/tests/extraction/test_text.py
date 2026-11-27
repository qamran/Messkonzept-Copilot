"""MKC-22: `extract_text` (feature 29): title, applications, footnotes, stated LBS.

Pinned interface (module `mkc.extraction.text`):

    extract_text(pdf: bytes, region: ConceptRegion) -> TextFields

`TextFields` and `StatedLbs` are frozen Pydantic models:

- `title`: the heading without its number; a title that wraps is joined with one space.
- `applications`: the `Anwendung:` bullets, without the bullet sign, in order; the `LBS`
  bullets are not applications.
- `footnotes`: one entry per `*n)` footnote, starting with its marker; the lines that go on
  below it are joined with one space.
- `stated_lbs`: one `StatedLbs(code, condition)` per `LBS` bullet, in order; `code` is the 13
  digits without spaces, `condition` the text in brackets after it, or None.

Only words inside `region.bbox` count (`(x0, top, x1, bottom)`, top-left origin, as
`segment_document` gives it): the sidebar's words on the same lines stay out. Diagram labels
(`Z 1`, `G`, `*1`) are none of the four fields.
"""

from typing import Any

from tests.extraction.synthetic import (
    APPLICATIONS,
    CONCEPT_BBOX,
    FOOTNOTES,
    STATED,
    TITLE,
    concept_page_pdf,
)


def _region(page: int, number: str) -> Any:
    from mkc.extraction.segment import ConceptRegion

    return ConceptRegion(page=page, bbox=CONCEPT_BBOX, number_hint=number)


def test_stated_lbs_parsed() -> None:
    from mkc.extraction.text import extract_text

    fields = extract_text(concept_page_pdf(), _region(1, "4.4"))
    assert [(s.code, s.condition) for s in fields.stated_lbs] == STATED


def test_a_stated_code_without_a_condition() -> None:
    from mkc.extraction.text import extract_text

    fields = extract_text(concept_page_pdf(), _region(2, "3"))
    assert [(s.code, s.condition) for s in fields.stated_lbs] == [("9992000000133", None)]
    assert fields.title == "Überschusseinspeisung mit Erzeugungsmessung"
    assert fields.applications == ["PV-Anlagen"]


def test_text_fields_of_a_concept_page() -> None:
    from mkc.extraction.text import extract_text

    fields = extract_text(concept_page_pdf(), _region(1, "4.4"))
    assert fields.title == TITLE
    assert fields.applications == APPLICATIONS
    assert fields.footnotes == FOOTNOTES


def test_the_sidebar_stays_out() -> None:
    from mkc.extraction.text import extract_text

    fields = extract_text(concept_page_pdf(), _region(1, "4.4"))
    dumped = fields.model_dump_json()
    for word in ("Messkonzepte", "Seite/Umfang", "Ausgabe", "Zuständig"):
        assert word not in dumped


def test_extract_text_is_deterministic() -> None:
    from mkc.extraction.text import extract_text

    region = _region(1, "4.4")
    first = extract_text(concept_page_pdf(), region)
    again = extract_text(concept_page_pdf(), region)
    assert again == first
    assert again.model_dump(mode="json") == first.model_dump(mode="json")
