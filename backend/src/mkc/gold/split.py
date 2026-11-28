"""The gold dev/test split (MKC-24.1, design 11.1, decision 75).

A key is `<operator id>:<number hint>`. Per operator, the keys are ranked by the SHA-256 of
the key (never Python's `hash()`, never their number, so the split depends on neither the
hash seed nor the order of the catalogue) and the first `ceil(n/2)` go to dev. Pinned keys
(lane A's MKC-25 concepts) always go to dev: dev is the pins plus the best-ranked unpinned
keys up to `ceil(n/2)`. Pins that the split already puts in dev therefore change nothing.

The file is written by `dump_split` and read by `load_split`; it holds the keys, their side
and the pins, so it can be written again from itself.
"""

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

Side = Literal["dev", "test"]

GOLD_SPLIT_FILE = Path(__file__).resolve().parents[3] / "data" / "gold_split.yaml"
"""The committed split (`backend/data/gold_split.yaml`), fixed before any prompt tuning."""

HEADER = (
    "# Gold dev/test split (MKC-24, design 11.1, decision 75). Keys only.\n"
    "# Written by `mkc gold split`; do not edit by hand. Tune on dev, report on test.\n"
)


@dataclass(frozen=True)
class GoldSplit:
    assignments: Mapping[str, Side]  # key -> side, every key once
    pinned_dev: tuple[str, ...]  # sorted


def concept_key(operator_id: str, number_hint: str) -> str:
    """`stromnetz-berlin:4.1`."""
    return f"{operator_id}:{number_hint}"


def operator_of(key: str) -> str:
    """The operator id of a key (the part before the first colon)."""
    operator, sep, hint = key.partition(":")
    if not sep or not operator or not hint:
        raise ValueError(f"not a concept key (<operator>:<number>): {key!r}")
    return operator


def _rank(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _natural(key: str) -> tuple[object, ...]:
    """Sort order for the file: operator, then the number hint as numbers (`2` before `10`)."""
    operator, _, hint = key.partition(":")
    parts = re.split(r"(\d+)", hint)
    return (operator, *((0, int(p), "") if p.isdigit() else (1, 0, p) for p in parts if p))


def split_keys(keys: Iterable[str], *, pinned_dev: Iterable[str] = ()) -> GoldSplit:
    """Each key to `dev` or `test`, about 50/50 per operator, pinned keys in dev.

    Raises `ValueError` for a key without an operator, a pin that is not a key, or more pins
    than `ceil(n/2)` of an operator's keys."""
    all_keys = sorted(set(keys))
    by_operator: dict[str, list[str]] = {}
    for key in all_keys:
        by_operator.setdefault(operator_of(key), []).append(key)
    pins = sorted(set(pinned_dev))
    unknown = [p for p in pins if p not in set(all_keys)]
    if unknown:
        raise ValueError(f"pinned key not among the keys: {', '.join(unknown)}")
    assignments: dict[str, Side] = {}
    for operator, members in sorted(by_operator.items()):
        dev_size = math.ceil(len(members) / 2)
        own_pins = [p for p in pins if operator_of(p) == operator]
        if len(own_pins) > dev_size:
            raise ValueError(
                f"{len(own_pins)} pins for {operator}, but dev holds {dev_size} of its "
                f"{len(members)} keys"
            )
        ranked = sorted((k for k in members if k not in own_pins), key=_rank)
        dev = set(own_pins) | set(ranked[: dev_size - len(own_pins)])
        for key in members:
            assignments[key] = "dev" if key in dev else "test"
    return GoldSplit(assignments=assignments, pinned_dev=tuple(pins))


def dump_split(split: GoldSplit) -> str:
    """The file text: a header, the pins, then the dev and test keys in natural order."""
    ordered = sorted(split.assignments, key=_natural)
    body = {
        "pinned_dev": sorted(split.pinned_dev, key=_natural),
        "dev": [k for k in ordered if split.assignments[k] == "dev"],
        "test": [k for k in ordered if split.assignments[k] == "test"],
    }
    text = yaml.safe_dump(body, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return HEADER + text


def load_split(path: Path = GOLD_SPLIT_FILE) -> GoldSplit:
    """Read a split file. Raises `ValueError` when a key is on both sides or a pin is not
    in dev."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    dev = [str(k) for k in data.get("dev") or []]
    test = [str(k) for k in data.get("test") or []]
    pins = tuple(sorted(str(k) for k in data.get("pinned_dev") or []))
    both = sorted(set(dev) & set(test))
    if both:
        raise ValueError(f"{path}: keys on both sides: {', '.join(both)}")
    stray = [p for p in pins if p not in set(dev)]
    if stray:
        raise ValueError(f"{path}: pinned keys not in dev: {', '.join(stray)}")
    assignments: dict[str, Side] = {k: "dev" for k in dev}
    assignments.update({k: "test" for k in test})
    return GoldSplit(assignments=assignments, pinned_dev=pins)
