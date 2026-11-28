"""MKC-24 success criterion "Split file committed (keys only, no PDF content)", lane A2.

The split is fixed in the repo before any prompt tuning (design 11.1): `GOLD_SPLIT_FILE`
(`backend/data/gold_split.yaml`), written by `mkc gold split`. It holds keys, their side and
the pinned dev keys, nothing else. Concept keys come from the segmenters: Berlin's 26 number
hints (live, `test_live_berlin.EXPECTED_BERLIN_CONCEPTS`) and SachsenNetze's 11 (MKC-27,
the placeholder `13 / Nr. (tbd)` excluded).
"""

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[2]
SPLIT_FILE = BACKEND / "data" / "gold_split.yaml"
OPERATORS_FILE = BACKEND / "data" / "operators.yaml"

BERLIN_CONCEPTS = 26
SACHSEN_HINTS = {"2-1", "2-1a", "2-2", "2-2a", "2-3", "2-3a", "2-3b", "2-5a", "3-1", "3-2", "3-5"}
KEY = re.compile(r"^[a-z0-9-]+:[0-9A-Za-z.-]{1,12}$")


def _load() -> Any:
    from mkc.gold.split import load_split

    return load_split(SPLIT_FILE)


def _by_operator(assignments: Any) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for key, side in assignments.items():
        operator, hint = key.split(":", 1)
        found.setdefault(operator, {})[hint] = side
    return found


def test_the_module_points_at_the_committed_file() -> None:
    from mkc.gold.split import GOLD_SPLIT_FILE

    assert Path(GOLD_SPLIT_FILE).resolve() == SPLIT_FILE


def test_split_file_is_committed_with_both_operators() -> None:
    assert SPLIT_FILE.is_file(), "commit backend/data/gold_split.yaml (`mkc gold split`)"
    operators = {o["id"] for o in yaml.safe_load(OPERATORS_FILE.read_text("utf-8"))["operators"]}
    by_operator = _by_operator(_load().assignments)
    assert set(by_operator) == operators
    assert set(by_operator["sachsennetze"]) == SACHSEN_HINTS
    assert "13" not in by_operator["sachsennetze"]
    assert len(by_operator["stromnetz-berlin"]) == BERLIN_CONCEPTS


def test_split_file_is_balanced_per_operator_and_keeps_its_pins() -> None:
    split = _load()
    for operator, hints in _by_operator(split.assignments).items():
        count = Counter(hints.values())
        assert set(count) <= {"dev", "test"}, operator
        assert abs(count["dev"] - count["test"]) <= 1, (operator, count)
    assert all(split.assignments[k] == "dev" for k in split.pinned_dev)


def test_split_file_is_what_the_split_writes_from_its_own_keys() -> None:
    """Regenerating from the file's keys and pins gives the file, byte for byte."""
    from mkc.gold.split import dump_split, split_keys

    split = _load()
    again = dump_split(split_keys(list(split.assignments), pinned_dev=list(split.pinned_dev)))
    assert SPLIT_FILE.read_bytes() == again.encode("utf-8")


def test_split_file_holds_keys_only() -> None:
    raw = SPLIT_FILE.read_bytes()
    assert b"\r" not in raw
    assert len(raw) < 8_000, "a split of about 40 keys is small; no PDF content"
    text = raw.decode("utf-8")
    assert "base64" not in text and "data:" not in text
    assert all(len(line) <= 100 for line in text.splitlines())
    split = _load()
    assert all(KEY.fullmatch(k) for k in split.assignments), "keys only"
    assert set(split.assignments.values()) <= {"dev", "test"}
