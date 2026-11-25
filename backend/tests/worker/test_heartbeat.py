"""MKC-9.1: the worker writes a heartbeat file; `mkc-worker-health` checks it.

The worker pod has no HTTP port, so its Kubernetes probe runs `mkc-worker-health`.
"""

import os
import threading
import time
from pathlib import Path

import pytest

from mkc.worker import health
from mkc.worker.main import run

OLD = 1_000_000_000.0  # 2001: far older than any max age


def _run_briefly(seconds: float, during: threading.Timer | None = None) -> None:
    stop = threading.Event()
    stopper = threading.Timer(seconds, stop.set)
    stopper.start()
    if during:
        during.start()
    try:
        run(stop)
    finally:
        stopper.cancel()
        if during:
            during.cancel()


def test_worker_writes_heartbeat_on_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    beat = tmp_path / "heartbeat"
    monkeypatch.setenv("MKC_WORKER_HEARTBEAT_FILE", str(beat))
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    before = time.time()

    _run_briefly(0.2)

    assert beat.is_file()
    assert beat.stat().st_mtime >= before - 1


def test_worker_refreshes_heartbeat_on_every_poll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beat = tmp_path / "heartbeat"
    monkeypatch.setenv("MKC_WORKER_HEARTBEAT_FILE", str(beat))
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    aged = threading.Event()

    def age_it() -> None:  # after a few polls, make the file look old
        os.utime(beat, (OLD, OLD))
        aged.set()

    _run_briefly(0.6, during=threading.Timer(0.2, age_it))

    assert aged.is_set()
    assert beat.stat().st_mtime > OLD + 1  # a later poll touched it again


def test_no_heartbeat_file_when_not_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MKC_WORKER_HEARTBEAT_FILE", raising=False)
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    monkeypatch.chdir(tmp_path)

    _run_briefly(0.15)

    assert list(tmp_path.iterdir()) == []


def test_fresh_heartbeat_is_healthy(tmp_path: Path) -> None:
    beat = tmp_path / "heartbeat"
    beat.touch()
    assert health.is_fresh(beat, max_age_seconds=30)


def test_stale_heartbeat_is_unhealthy(tmp_path: Path) -> None:
    beat = tmp_path / "heartbeat"
    beat.touch()
    os.utime(beat, (OLD, OLD))
    assert not health.is_fresh(beat, max_age_seconds=30)


def test_missing_heartbeat_is_unhealthy(tmp_path: Path) -> None:
    assert not health.is_fresh(tmp_path / "missing", max_age_seconds=30)


def test_health_command_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    beat = tmp_path / "heartbeat"
    monkeypatch.setenv("MKC_WORKER_HEARTBEAT_FILE", str(beat))
    monkeypatch.setenv("MKC_WORKER_HEARTBEAT_MAX_AGE_SECONDS", "30")

    assert health.main() == 1  # missing
    beat.touch()
    assert health.main() == 0  # fresh
    os.utime(beat, (OLD, OLD))
    assert health.main() == 1  # stale


def test_health_command_fails_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MKC_WORKER_HEARTBEAT_FILE", raising=False)
    assert health.main() == 1
