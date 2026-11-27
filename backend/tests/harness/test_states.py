"""MKC-15.1: run and item states, one transition function, tested against the table."""

from itertools import product

import pytest

from mkc.harness.states import (
    EDGES,
    TERMINAL,
    InvalidTransition,
    ItemState,
    RunState,
    transition,
)

# The edge table of decision 54 (design 8.2), written out again on purpose: the test
# compares the code against the design, not against itself.
DESIGN_EDGES: set[tuple[str, str]] = {
    ("queued", "running"),
    ("running", "draft_saved"),
    ("running", "failed"),
    ("draft_saved", "pending_approval"),
    ("pending_approval", "approved"),
    ("pending_approval", "rejected"),
    ("approved", "committed"),
}
DESIGN_RUN_EDGES: set[tuple[str, str]] = {
    ("running", "awaiting_approval"),
    ("running", "done"),
    ("running", "stopped"),
    ("awaiting_approval", "done"),
    ("running", "waiting_for_database"),  # MKC-17, decision 57
    ("waiting_for_database", "running"),
}


def test_enum_values_are_the_design_names() -> None:
    assert {s.value for s in ItemState} == {
        "queued",
        "running",
        "draft_saved",
        "pending_approval",
        "approved",
        "committed",
        "rejected",
        "failed",
    }
    assert {s.value for s in RunState} == {
        "running",
        "awaiting_approval",
        "done",
        "stopped",
        "waiting_for_database",
    }


def test_edge_table_matches_the_design() -> None:
    item = {(a.value, b.value) for a, b in EDGES if isinstance(a, ItemState)}
    run = {(a.value, b.value) for a, b in EDGES if isinstance(a, RunState)}
    assert item == DESIGN_EDGES
    assert run == DESIGN_RUN_EDGES


@pytest.mark.parametrize(("current", "target"), sorted(DESIGN_EDGES))
def test_every_item_edge_is_allowed(current: str, target: str) -> None:
    assert transition(ItemState(current), ItemState(target)) is ItemState(target)


@pytest.mark.parametrize(("current", "target"), sorted(DESIGN_RUN_EDGES))
def test_every_run_edge_is_allowed(current: str, target: str) -> None:
    assert transition(RunState(current), RunState(target)) is RunState(target)


def test_invalid_state_transition_raises() -> None:
    with pytest.raises(InvalidTransition, match="queued -> committed"):
        transition(ItemState.QUEUED, ItemState.COMMITTED)


def test_every_pair_not_in_the_table_is_refused() -> None:
    refused = 0
    for enum, edges in ((ItemState, DESIGN_EDGES), (RunState, DESIGN_RUN_EDGES)):
        for a, b in product(enum, enum):  # type: ignore[var-annotated]
            if (a.value, b.value) in edges:
                continue
            with pytest.raises(InvalidTransition):
                transition(a, b)
            refused += 1
    assert refused == 8 * 8 - 7 + 5 * 5 - 6


def test_item_and_run_states_do_not_mix() -> None:
    with pytest.raises(InvalidTransition):
        transition(RunState.RUNNING, ItemState.FAILED)  # type: ignore[call-overload]


def test_terminal_states_have_no_outgoing_edges() -> None:
    assert {s.value for s in TERMINAL} == {"committed", "rejected", "failed", "done", "stopped"}
    assert not [edge for edge in EDGES if edge[0] in TERMINAL]
