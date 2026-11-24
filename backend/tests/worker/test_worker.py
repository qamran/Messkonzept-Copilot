"""MKC-4.2: the worker starts and exits cleanly on SIGTERM."""

import os
import signal
import subprocess
import sys
import threading
import time

import pytest

from mkc.worker.main import run


def test_run_stops_on_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    timer = threading.Timer(0.2, signal.raise_signal, args=(signal.SIGTERM,))
    previous = signal.getsignal(signal.SIGTERM)

    timer.start()
    started = time.monotonic()
    run()
    elapsed = time.monotonic() - started

    assert elapsed < 5
    assert signal.getsignal(signal.SIGTERM) == previous  # handlers restored


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="On Windows, SIGTERM from another process terminates without running a handler",
)
def test_worker_process_exits_cleanly_on_sigterm() -> None:
    env = {**os.environ, "MKC_WORKER_POLL_SECONDS": "0.05", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "mkc.worker.main"],
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert proc.stderr is not None
        assert "worker started" in proc.stderr.readline()
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
