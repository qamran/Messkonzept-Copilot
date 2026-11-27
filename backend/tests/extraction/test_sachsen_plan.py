"""MKC-27 success criterion: the split method (detected layout vs half page) is documented in the
ticket plan, with the reason. Pinned as a small check; the quality of the reason stays a review
item."""

import re
from pathlib import Path

PLANS = Path(__file__).resolve().parents[3] / "docs" / "superpowers" / "plans"
PLAN = re.compile(r"\d{12}-mkc-27-sachsen-segmentation\.md")


def test_the_ticket_plan_names_the_split_method_and_the_reason() -> None:
    found = [p for p in PLANS.iterdir() if PLAN.fullmatch(p.name)]
    assert len(found) == 1, "docs/superpowers/plans/<ddMMyyyyHHmm>-mkc-27-sachsen-segmentation.md"
    text = found[0].read_text(encoding="utf-8").lower()
    assert "detected layout" in text or "half page" in text, "names the method chosen"
    assert "because" in text or "reason" in text, "gives the reason"
