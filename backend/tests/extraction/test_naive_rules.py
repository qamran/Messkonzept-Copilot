"""MKC-22.2: the naive baseline's meter-tech rows stay on the page of their heading
(decision 77 (7)): a later page's concept title or appendix row is no meter row."""

from tests.extraction.conftest import Text, layout_pdf


def test_a_meter_heading_ends_with_its_page() -> None:
    from mkc.extraction.naive import naive_tables

    pdf = layout_pdf(
        [[Text(57, 100, "Erzeugungsmessung (Z2)", 10), Text(57, 120, "3 2RZ 60 A 2RZ 100A", 10)],
         [Text(57, 100, "3 Überschusseinspeisung mit Erzeugungsmessung", 10),
          Text(57, 120, "11.1 2RZ 60 A", 10)]]
    )  # fmt: skip
    rows = naive_tables(pdf, "meter_tech")
    assert [(r.page, r.concepts, r.label) for r in rows] == [(1, ["3"], "Erzeugungsmessung (Z2)")]
