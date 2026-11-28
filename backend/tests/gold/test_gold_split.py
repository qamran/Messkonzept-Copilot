"""MKC-24: the gold dev/test split (feature 33, design 11.1), lane A2.

Pinned interface (module `mkc.gold.split`):

    concept_key(operator_id: str, number_hint: str) -> str     # "stromnetz-berlin:4.1"
    split_keys(keys: Iterable[str], *, pinned_dev: Iterable[str] = ()) -> GoldSplit
    GoldSplit.assignments: Mapping[str, str]   # key -> "dev" | "test", every key once
    GoldSplit.pinned_dev: tuple[str, ...]      # the pinned keys, sorted
    dump_split(split: GoldSplit) -> str        # the file text (YAML), byte for byte stable
    load_split(path: Path) -> GoldSplit        # reads what dump_split wrote

A key is `<operator id>:<number hint>`; the operator is the part before the first colon.
About 50/50 per operator: for each operator |dev - test| <= 1. Pinned keys (lane A's MKC-25
go/no-go concepts) always land in dev. Deterministic: the same keys and pins give the same
text in any input order, under any hash seed, with no time or randomness in it.
"""

import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

BERLIN = [f"stromnetz-berlin:{n}" for n in ("1", "2", "3", "4.1", "4.2", "5", "6a")]
SACHSEN = [
    f"sachsennetze:{n}"
    for n in ("2-1", "2-1a", "2-2", "2-2a", "2-3", "2-3a", "2-3b", "2-5a", "3-1", "3-2", "3-5")
]
KEYS = BERLIN + SACHSEN


def _split(keys: Any, **kwargs: Any) -> Any:
    from mkc.gold.split import split_keys

    return split_keys(keys, **kwargs)


def _dump(split: Any) -> str:
    from mkc.gold.split import dump_split

    return str(dump_split(split))


def _per_operator(assignments: Any) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {}
    for key, side in assignments.items():
        counts.setdefault(key.split(":", 1)[0], Counter())[side] += 1
    return counts


def _assert_balanced(assignments: Any) -> None:
    for operator, count in _per_operator(assignments).items():
        assert set(count) <= {"dev", "test"}, (operator, count)
        assert abs(count["dev"] - count["test"]) <= 1, (operator, count)


def test_split_is_deterministic_and_balanced_per_operator() -> None:
    split = _split(KEYS)
    assert sorted(split.assignments) == sorted(KEYS)
    _assert_balanced(split.assignments)
    assert _per_operator(split.assignments)["sachsennetze"].total() == 11

    shuffled = list(KEYS)
    random.Random(7).shuffle(shuffled)
    assert _dump(_split(shuffled)) == _dump(split)
    assert _dump(_split(tuple(reversed(KEYS)))) == _dump(split)
    assert _dump(_split(KEYS)) == _dump(split)


def test_concept_key_is_operator_colon_number_hint() -> None:
    from mkc.gold.split import concept_key

    assert concept_key("stromnetz-berlin", "4.1") == "stromnetz-berlin:4.1"
    assert concept_key("sachsennetze", "2-1a") == "sachsennetze:2-1a"


def test_balance_is_per_operator_not_over_all_keys() -> None:
    # Sorted over all keys, the a-operator's keys come first: a global first-half split
    # would put all of them in dev.
    keys = [f"a-op:{n}" for n in range(1, 7)] + [f"z-op:{n}" for n in range(1, 7)]
    split = _split(keys)
    counts = _per_operator(split.assignments)
    assert counts["a-op"] == Counter(dev=3, test=3)
    assert counts["z-op"] == Counter(dev=3, test=3)


@pytest.mark.parametrize("seed", range(20))
def test_balance_holds_for_any_count(seed: int) -> None:
    rng = random.Random(seed)
    keys = [f"op{o}:{n}" for o in range(rng.randint(1, 4)) for n in range(rng.randint(1, 15))]
    split = _split(keys)
    assert sorted(split.assignments) == sorted(keys)
    _assert_balanced(split.assignments)


def test_one_key_alone_goes_to_one_side() -> None:
    split = _split(["solo-op:1"])
    assert dict(split.assignments) in ({"solo-op:1": "dev"}, {"solo-op:1": "test"})


def test_pinned_keys_land_in_dev_and_balance_still_holds() -> None:
    unpinned = _split(KEYS).assignments
    pinned = sorted(k for k in BERLIN if unpinned[k] == "test")[:3]
    assert pinned, "the unpinned split puts no Berlin key in test; pick other keys"
    split = _split(KEYS, pinned_dev=pinned)
    assert all(split.assignments[k] == "dev" for k in pinned)
    _assert_balanced(split.assignments)
    assert tuple(split.pinned_dev) == tuple(sorted(pinned))


def test_five_pinned_berlin_concepts_of_twenty_six() -> None:
    # The real shape: 26 Berlin concepts, lane A's MKC-25 names 5 of them for dev.
    berlin = [f"stromnetz-berlin:{n}" for n in range(1, 27)]
    pinned = [f"stromnetz-berlin:{n}" for n in (2, 4, 6, 8, 10)]
    split = _split(berlin + SACHSEN, pinned_dev=pinned)
    assert all(split.assignments[k] == "dev" for k in pinned)
    counts = _per_operator(split.assignments)
    assert counts["stromnetz-berlin"] == Counter(dev=13, test=13)
    _assert_balanced(split.assignments)


def test_pinning_is_deterministic() -> None:
    pinned = ["stromnetz-berlin:2", "stromnetz-berlin:5"]
    first = _dump(_split(KEYS, pinned_dev=pinned))
    shuffled = list(KEYS)
    random.Random(3).shuffle(shuffled)
    assert _dump(_split(shuffled, pinned_dev=list(reversed(pinned)))) == first


def test_pinning_keys_already_in_dev_changes_nothing() -> None:
    """Pins that agree with the split leave every other key where it was, so naming the
    MKC-25 concepts later does not move keys between dev and test without need."""
    unpinned = _split(KEYS).assignments
    already_dev = sorted(k for k, side in unpinned.items() if side == "dev")[:4]
    pinned = _split(KEYS, pinned_dev=already_dev).assignments
    assert dict(pinned) == dict(unpinned)


def test_unknown_pinned_key_is_refused() -> None:
    with pytest.raises(ValueError, match="stromnetz-berlin:99"):
        _split(KEYS, pinned_dev=["stromnetz-berlin:99"])


def test_more_pins_than_half_an_operator_is_refused() -> None:
    # 7 Berlin keys: dev may hold at most 4. Five pins break the balance or the pins.
    with pytest.raises(ValueError):
        _split(KEYS, pinned_dev=BERLIN[:5])


def test_a_key_without_an_operator_is_refused() -> None:
    with pytest.raises(ValueError):
        _split([*KEYS, "4.1"])


def test_dump_and_load_round_trip(tmp_path: Path) -> None:
    from mkc.gold.split import load_split

    split = _split(KEYS, pinned_dev=["stromnetz-berlin:2"])
    path = tmp_path / "gold_split.yaml"
    path.write_text(_dump(split), encoding="utf-8", newline="\n")
    loaded = load_split(path)
    assert dict(loaded.assignments) == dict(split.assignments)
    assert tuple(loaded.pinned_dev) == ("stromnetz-berlin:2",)


def test_dump_has_no_carriage_return_and_ends_with_one_newline() -> None:
    text = _dump(_split(KEYS))
    assert "\r" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")


SUBPROCESS = """
import sys
from mkc.gold.split import dump_split, split_keys
keys = sys.argv[1].split(",")
sys.stdout.buffer.write(dump_split(split_keys(keys, pinned_dev=["stromnetz-berlin:2"])).encode())
"""


def test_dump_is_the_same_under_any_hash_seed() -> None:
    """No dict or set order leaks into the file: two interpreters with different hash seeds
    write the same bytes."""
    outputs = []
    for seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", SUBPROCESS, ",".join(KEYS)],
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0]
