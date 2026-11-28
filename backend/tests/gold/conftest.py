"""Shared helpers for the MKC-24 gold tests (lane A2).

`mkc.gold` does not exist when these tests are written, so every test imports it inside the
test (one red test each, not one collection error for the file).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.harness.conftest import engine

__all__ = ["engine"]

SENTINEL = "SENTINEL"
"""Every draft-only value of `draft_payload` contains this word, so a blind export can be
checked on its raw bytes: the word must not appear anywhere in it."""

SENTINEL_LBS = "9907654321098"
"""The draft's LBS code: 13 digits, so it cannot carry the sentinel word."""


def draft_payload(**overrides: Any) -> dict[str, Any]:
    """A payload that validates as `MesskonzeptDraft`. Operator, number and source (key,
    concept and page reference) are plain; every other value holds `SENTINEL`."""
    payload: dict[str, Any] = {
        "operator": "Stromnetz Berlin GmbH",
        "number": "4.1",
        "title": f"{SENTINEL}-TITLE Ueberschusseinspeisung",
        "applications": [f"{SENTINEL}-APPLICATION PV-Anlage"],
        "meters": [
            {
                "label": f"Z1{SENTINEL}",
                "purpose": "Zweirichtung",
                "directions": ["Bezug", "Einspeisung"],
                "upstream": None,
                "types": [{"band": f"{SENTINEL}-BAND <= 100 kW", "type": f"{SENTINEL}-2RZ"}],
            }
        ],
        "components": [{"kind": "G", "attached_to": f"Z1{SENTINEL}"}],
        "formulas": [{"expression": f"{SENTINEL}-FORMULA Z1.1", "provenance": "printed"}],
        "lbs": [
            {
                "code": SENTINEL_LBS,
                "condition": f"{SENTINEL}-CONDITION",
                "provenance": "stated",
                "rationale": f"{SENTINEL}-RATIONALE",
            }
        ],
        "footnotes": [f"{SENTINEL}-FOOTNOTE"],
        "source": {"document": "sha256:berlin-2026-09", "page": 12},
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def gold_engine(engine: Engine) -> Iterator[Engine]:
    """The migrated test database with an empty `gold_item` table."""
    with engine.begin() as conn:
        conn.execute(text("truncate gold_item restart identity"))
    yield engine
