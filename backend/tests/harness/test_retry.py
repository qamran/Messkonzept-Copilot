"""MKC-18.3: retries of model calls with exponential backoff and a turn deadline."""

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

from mkc.harness.limits import Limits
from mkc.harness.retry import RetriesExhausted, RetryInterrupted, call_model
from mkc.models.types import TransientModelError


class Clock:
    """A fake sleep: records each wait; `interrupt_at` makes that wait report a shutdown."""

    def __init__(self, interrupt_at: int | None = None) -> None:
        self.waits: list[float] = []
        self.interrupt_at = interrupt_at

    def __call__(self, seconds: float) -> bool:
        self.waits.append(seconds)
        return self.interrupt_at is not None and len(self.waits) >= self.interrupt_at


def failing(times: int, error: Exception | None = None, result: Any = "reply") -> Any:
    """A model call that raises `error` (a 429 by default) `times` times, then returns."""
    calls = {"n": 0}

    def fn() -> Any:
        calls["n"] += 1
        if calls["n"] <= times:
            raise error or TransientModelError("HTTP 429")
        return result

    fn.calls = calls  # type: ignore[attr-defined]
    return fn


def go(fn: Callable[[], Any], clock: Clock, limits: Limits | None = None,
       should_stop: Callable[[], bool] = lambda: False) -> Any:  # fmt: skip
    return call_model(fn, limits=limits or Limits(), sleep=clock, should_stop=should_stop)


def test_429_backs_off_exponentially() -> None:
    clock = Clock()
    assert go(failing(4), clock) == "reply"
    assert clock.waits == [2, 4, 8, 16]  # base 2 s, doubling (decision 58)


def test_the_wait_is_capped() -> None:
    clock = Clock()
    go(failing(4), clock, Limits(backoff_base_s=2, backoff_max_s=5))
    assert clock.waits == [2, 4, 5, 5]


def test_retries_run_out() -> None:
    clock = Clock()
    fn = failing(10)
    with pytest.raises(RetriesExhausted) as caught:
        go(fn, clock, Limits(max_retries_model=2))
    assert clock.waits == [2, 4]
    assert fn.calls["n"] == 3 and caught.value.attempts == 3
    assert isinstance(caught.value.__cause__, TransientModelError)


def test_no_retry_when_max_retries_is_zero() -> None:
    clock = Clock()
    with pytest.raises(RetriesExhausted):
        go(failing(1), clock, Limits(max_retries_model=0))
    assert clock.waits == []


@pytest.mark.parametrize(("retry_after", "wait"), [(30.0, 30.0), (1.0, 2.0), (600.0, 60.0)])
def test_retry_after_wins_when_longer_and_is_capped(retry_after: float, wait: float) -> None:
    clock = Clock()
    go(failing(1, TransientModelError("HTTP 429", retry_after=retry_after)), clock)
    assert clock.waits == [wait]


def test_other_errors_are_not_retried() -> None:
    clock = Clock()
    fn = failing(1, ValueError("bad reply"))
    with pytest.raises(ValueError, match="bad reply"):
        go(fn, clock)
    assert clock.waits == [] and fn.calls["n"] == 1


def test_should_stop_ends_the_retries_before_a_wait() -> None:
    clock = Clock()
    fn = failing(3)
    with pytest.raises(RetryInterrupted):
        go(fn, clock, should_stop=lambda: True)
    assert clock.waits == [] and fn.calls["n"] == 1


def test_a_shutdown_during_the_wait_ends_the_retries() -> None:
    clock = Clock(interrupt_at=2)  # SIGTERM arrives during the second wait
    fn = failing(5)
    with pytest.raises(RetryInterrupted):
        go(fn, clock)
    assert clock.waits == [2, 4] and fn.calls["n"] == 2


def test_the_turn_deadline_turns_a_hung_call_into_a_timeout() -> None:
    release = threading.Event()

    def hung() -> str:
        release.wait(10)
        return "too late"

    started = time.monotonic()
    try:
        with pytest.raises(RetriesExhausted) as caught:
            go(hung, Clock(), Limits(turn_timeout_s=0.2, max_retries_model=0))
    finally:
        release.set()
    assert time.monotonic() - started < 2
    assert "deadline" in str(caught.value.__cause__)


def test_a_call_under_the_deadline_returns_its_reply_and_raises_its_error() -> None:
    limits = Limits(turn_timeout_s=5)
    assert go(lambda: "fast", Clock(), limits) == "fast"
    with pytest.raises(KeyError):
        go(failing(1, KeyError("boom")), Clock(), limits)
