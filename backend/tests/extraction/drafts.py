"""A valid `MesskonzeptDraft` body for the MKC-23 tests (design section 7), in one place.

Every guessed nested name lives here, so a coordinator ruling on a name changes one line:
meters have `label`, `purpose`, `directions` and `upstream` (None at the grid connection);
components have `kind` and `attached_to`; an LBS entry has `code`, `condition`,
`provenance` and `rationale`; `source` has `document` and `page`.
"""

from typing import Any

DRAFT_FIELDS = {
    "operator",
    "number",
    "title",
    "applications",
    "meters",
    "components",
    "formulas",
    "lbs",
    "footnotes",
    "source",
}
"""Section 7's Messkonzept fields without `status`, `approved_by` and `approved_at`: those
belong to the approval, and the model must not be able to set them (MKC-23 assumption)."""

PURPOSES = ("Bezug", "Einspeisung", "Zweirichtung", "Erzeugung", "Abgrenzung", "sVE")
COMPONENT_KINDS = ("G", "B", "WR", "SE", "SV", "sVE", "S")


def valid_draft(title: str = "Ueberschusseinspeisung mit Erzeugungsmessung") -> dict[str, Any]:
    """A complete draft as the model would send it to `save_draft` (`formulas` left out:
    section 7 marks it optional)."""
    return {
        "operator": "stromnetz-berlin",
        "number": "3.2",
        "title": title,
        "applications": ["PV-Anlage mit Ueberschusseinspeisung"],
        "meters": [
            {
                "label": "Z1",
                "purpose": "Zweirichtung",
                "directions": ["Bezug", "Einspeisung"],
                "upstream": None,
            },
            {
                "label": "Z2",
                "purpose": "Erzeugung",
                "directions": ["Einspeisung"],
                "upstream": "Z1",
            },
        ],
        "components": [{"kind": "G", "attached_to": "Z2"}, {"kind": "WR", "attached_to": "Z2"}],
        "lbs": [
            {
                "code": "9992000000133",
                "condition": "mit gemessener Erzeugung",
                "provenance": "stated",
                "rationale": "printed in the concept's LBS bullet",
            }
        ],
        "footnotes": ["*1) Messung nach Vorgabe des Netzbetreibers"],
        "source": {"document": "sha256:doc", "page": 14},
    }
