"""Retries of model calls (MKC-18, design 8.5, decision 58)."""

from collections.abc import Callable

from mkc.harness.limits import Limits


class RetriesExhausted(Exception):
    """A transient error outlived every retry."""

    def __init__(self, attempts: int) -> None:
        super().__init__(f"no reply after {attempts} attempts")
        self.attempts = attempts


class RetryInterrupted(Exception):
    """Shutdown was requested while a call waited for its retry."""


def call_model[T](
    fn: Callable[[], T],
    *,
    limits: Limits,
    sleep: Callable[[float], bool],
    should_stop: Callable[[], bool],
) -> T:
    raise NotImplementedError
