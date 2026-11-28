"""MKC-25 sub-issue: `draft_locked` must hold for the whole key, not only for the last saver
(PR #225 review, non-blocking finding 1; must be fixed before MKC-29 approves anything).

Today `_check_writable` (`mkc/harness/drafts.py`) reads the state of `draft.item_id`, the item
that saved last. The reviewer's probe: item A saves `v1` and is `pending_approval` (the
`approval` row points at A); item B saves `v2` and then fails, so `draft.item_id` is B while
the `approval` row still points at A; A is approved; C's save is `ok` and the body becomes
`v3`. An approved draft was replaced.

Pinned (assumptions for the coordinator):

- Once ANY item of the key (same document hash and concept key) is `approved` or
  `committed`, or the key's `approval` row points at such an item, a later save is refused
  with `draft_locked` and nothing is written.
- "The approved body stays" is asserted as: the body after the refused save equals the body
  just before it (here `v2`, the body A's approval saw in the row). Whether MKC-29 should
  instead keep a snapshot of the body at approval time (`v1`) is the coordinator's call.
- Over-locking guards (green now, must stay green): a failed later saver does not lock while
  the queued item still waits; an approved item of another concept or another document does
  not lock this key.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.extraction.drafts import valid_draft
from tests.harness.conftest import make_run
from tests.harness.test_approvals import (
    bodies,
    env_for,
    item_row,
    queue_entries,
    save,
    saves,
    set_state,
)
from tests.harness.test_baseline import go, make
from tests.models.fakes import FakeChatModel


@pytest.fixture(autouse=True)
def empty_queue(engine: Engine) -> Iterator[None]:
    with engine.begin() as conn:
        conn.execute(text("truncate approval restart identity cascade"))
    yield


def titles(engine: Engine) -> list[str]:
    return [b["title"] for b in bodies(engine)]


def queued_item(engine: Engine) -> int:
    with engine.connect() as conn:
        (item_id,) = [r[0] for r in conn.execute(text("select item_id from approval"))]
        return int(item_id)


def pending_then_failed_saver(engine: Engine) -> tuple[int, int]:
    """A is `pending_approval` with `v1` queued; B (another run, same key) saves `v2` and
    fails. Returns (A, B). The draft row is B's, the queue row is A's."""
    first_run, (a,) = make(engine, 1, mode="full")
    go(engine, first_run, FakeChatModel(responses=[saves("v1")]))
    assert item_row(engine, a)[0] == "pending_approval"
    second_run, (b,) = make_run(engine, "running")
    result = save(engine, env_for(second_run, b), valid_draft("v2"))
    assert result.ok, result.error  # A still waits: the save may replace the body
    set_state(engine, b, "failed")
    assert titles(engine) == ["v2"]
    assert queued_item(engine) == a, "B never queued: the row still points at A"
    return a, b


def c_saves(engine: Engine, title: str = "v3") -> Any:
    run_id, (c,) = make_run(engine, "running")
    return save(engine, env_for(run_id, c), valid_draft(title))


@pytest.mark.parametrize("decided", ["approved", "committed"])
def test_the_queued_item_decided_locks_the_key_after_a_failed_saver(
    engine: Engine, decided: str
) -> None:
    """The reviewer's probe, exactly."""
    a, _ = pending_then_failed_saver(engine)
    set_state(engine, a, decided)
    before = titles(engine)
    result = c_saves(engine)
    assert result.error is not None and result.error.code == "draft_locked", result
    assert titles(engine) == before, "the body under approval was replaced"
    assert queue_entries(engine) == 1


@pytest.mark.parametrize("decided", ["approved", "committed"])
def test_any_decided_item_of_the_key_locks_it(engine: Engine, decided: str) -> None:
    """A pending, B saves `v2` and is queued too (draft and queue row both point at B), then
    the older A is approved (decision 83 (7): it stays `pending_approval`). C is refused."""
    first_run, (a,) = make(engine, 1, mode="full")
    go(engine, first_run, FakeChatModel(responses=[saves("v1")]))
    second_run, (b,) = make(engine, 1, mode="full")
    go(engine, second_run, FakeChatModel(responses=[saves("v2")]))
    assert item_row(engine, b)[0] == "pending_approval"
    assert queued_item(engine) == b
    set_state(engine, a, decided)
    result = c_saves(engine)
    assert result.error is not None and result.error.code == "draft_locked", result
    assert titles(engine) == ["v2"]
    assert queue_entries(engine) == 1


@pytest.mark.parametrize("decided", ["approved", "committed"])
def test_the_probe_through_the_loop_fails_the_item(engine: Engine, decided: str) -> None:
    a, _ = pending_then_failed_saver(engine)
    set_state(engine, a, decided)
    run_id, (c,) = make(engine, 1, mode="full")
    go(engine, run_id, FakeChatModel(responses=[saves("v3")]))
    state, reason = item_row(engine, c)
    assert state == "failed"
    assert reason is not None and "draft_locked" in reason
    assert titles(engine) == ["v2"]


# --- over-locking guards (green before and after the fix) --------------------------------


def test_a_failed_saver_does_not_lock_while_the_queued_item_waits(engine: Engine) -> None:
    pending_then_failed_saver(engine)
    result = c_saves(engine)
    assert result.ok, result.error
    assert titles(engine) == ["v3"]


@pytest.mark.parametrize(
    ("column", "value"), [("concept_key", "MK-2"), ("document_hash", "sha256:other")]
)
def test_an_approved_item_of_another_key_does_not_lock(
    engine: Engine, column: str, value: str
) -> None:
    pending_then_failed_saver(engine)
    _, (other,) = make_run(engine, "approved")
    with engine.begin() as conn:
        conn.execute(
            text(f"update item set {column} = :v where id = :id"), {"v": value, "id": other}
        )
    result = c_saves(engine)
    assert result.ok, result.error
    assert titles(engine) == ["v3"]
