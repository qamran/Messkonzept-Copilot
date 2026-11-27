"""MKC-18.4: no unexpected error ends a worker thread or the worker (MKC-17 finding 6).

Before: `_renew` caught only `SQLAlchemyError`, `_touch` only `OSError`, the claim in
`run_once` only `SQLAlchemyError`. Another error ended the thread (every run then lost its
lease after 120 s while the probe stayed green) or the worker.
"""

import time
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine

from mkc.worker import executor as executor_module
from tests.harness.conftest import make_run
from tests.harness.test_loop import SAVE
from tests.models.fakes import ai
from tests.worker.test_executor import HookModel, executor, turn_numbers


def once_then(real: Any, error: Exception) -> Any:
    """Raise `error` on the first call, then behave like `real`; counts the calls."""
    calls = {"n": 0}

    def fn(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise error
        return real(*args, **kwargs)

    fn.calls = calls  # type: ignore[attr-defined]
    return fn


def test_an_unexpected_renewal_error_does_not_end_the_lease_thread(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    make_run(engine, "queued")
    renew = once_then(executor_module.renew_lease, RuntimeError("driver bug"))
    monkeypatch.setattr("mkc.worker.executor.renew_lease", renew)
    model = HookModel(responses=[ai(tool_calls=[SAVE])], hooks={1: lambda: time.sleep(0.6)})
    with executor(engine, model, "w1", worker_lease_renew_seconds=0.1) as worker:
        assert worker.run_once() is True
        assert all(t.is_alive() for t in worker._threads)
    assert renew.calls["n"] >= 3  # it kept renewing after the error
    assert "driver bug" in caplog.text


class _FlakyFile:
    def __init__(self) -> None:
        self.touches = 0

    def touch(self) -> None:
        self.touches += 1
        if self.touches == 1:
            raise ValueError("odd path")


def test_an_unexpected_heartbeat_error_does_not_end_the_heartbeat_thread(
    engine: Engine, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    flaky = _FlakyFile()
    worker = executor(engine, HookModel(responses=[]), "w1",
                      worker_heartbeat_file=str(tmp_path / "beat"))  # fmt: skip
    worker._heartbeat_file = flaky  # type: ignore[assignment]
    with worker:
        time.sleep(0.3)  # poll interval 0.05 s
        assert all(t.is_alive() for t in worker._threads)
    assert flaky.touches >= 3
    assert "odd path" in caplog.text


def test_an_unexpected_claim_error_does_not_end_the_worker(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _, (item_id,) = make_run(engine, "queued")
    claim = once_then(executor_module.claim_run, RuntimeError("bad row"))
    monkeypatch.setattr("mkc.worker.executor.claim_run", claim)
    model = HookModel(responses=[ai(tool_calls=[SAVE])])
    with executor(engine, model, "w1", worker_db_backoff_max_seconds=0.1) as worker:
        assert worker.run_once() is False  # logged, not raised
        assert worker.run_once() is True  # the next poll claims the run
    assert turn_numbers(engine, item_id) == [1]
    assert "bad row" in caplog.text
