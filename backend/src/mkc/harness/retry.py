"""Retries of model calls (MKC-18, design 8.5, decision 58).

- Only `TransientModelError` is retried (`ModelClient` raises it for 408, 429, 5xx, timeouts
  and network errors) and a call that runs past the turn deadline. Every other error passes.
- Wait before retry n (0-based): `backoff_base_s * 2**n`, or `Retry-After` when longer, at
  most `backoff_max_s`. No jitter: one worker holds a run.
- `should_stop` is checked before each wait, and `sleep` returns True when shutdown cut the
  wait short (the executor passes `Executor.wait`), so SIGTERM never waits out a backoff.
- The deadline: the call runs in a daemon thread and the loop stops waiting after
  `turn_timeout_s`. A thread can't be killed, so the abandoned call may still finish and bill;
  its cost is lost from `turn.cost_eur` (known limit).
"""

import threading
from collections.abc import Callable
from typing import Any

from mkc.harness.limits import Limits
from mkc.models.types import TransientModelError


class RetriesExhausted(Exception):
    """A transient error outlived every retry; `__cause__` is the last one."""

    def __init__(self, attempts: int) -> None:
        super().__init__(f"no reply after {attempts} attempts")
        self.attempts = attempts


class RetryInterrupted(Exception):
    """Shutdown was requested while a call waited for its retry."""


def backoff_s(retry: int, limits: Limits, retry_after: float | None = None) -> float:
    """The wait before retry number `retry` (0-based)."""
    wait: float = max(limits.backoff_base_s * 2.0**retry, retry_after or 0.0)
    return min(wait, limits.backoff_max_s)


def call_model[T](
    fn: Callable[[], T],
    *,
    limits: Limits,
    sleep: Callable[[float], bool],
    should_stop: Callable[[], bool],
) -> T:
    """`fn()` under the turn deadline, retried on transient errors."""
    retry = 0
    while True:
        try:
            return with_deadline(fn, limits.turn_timeout_s)
        except TransientModelError as error:
            if retry >= limits.max_retries_model:
                raise RetriesExhausted(retry + 1) from error
            if should_stop() or sleep(backoff_s(retry, limits, error.retry_after)):
                raise RetryInterrupted from error
            retry += 1


def with_deadline[T](fn: Callable[[], T], seconds: float) -> T:
    """`fn()` in a daemon thread; `TransientModelError` if it has not returned in `seconds`."""
    done = threading.Event()
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["result"] = fn()
        except BaseException as error:  # handed to the caller's thread
            box["error"] = error
        finally:
            done.set()

    threading.Thread(target=target, name="mkc-model-call", daemon=True).start()
    if not done.wait(seconds):
        raise TransientModelError(f"no reply within the turn deadline of {seconds:g} s")
    if "error" in box:
        raise box["error"]
    result: T = box["result"]
    return result
