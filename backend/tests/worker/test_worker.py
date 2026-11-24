"""MKC-4.2: the worker starts and exits cleanly on SIGTERM."""

import os
import queue
import signal
import subprocess
import sys
import threading
import time

import pytest

from mkc.worker.main import run

TIMEOUT = 5.0


def test_run_stops_on_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    previous = signal.getsignal(signal.SIGTERM)
    stop = threading.Event()
    sigterm = threading.Timer(0.2, signal.raise_signal, args=(signal.SIGTERM,))
    watchdog = threading.Timer(TIMEOUT, stop.set)  # ends run() if SIGTERM is ignored

    sigterm.start()
    watchdog.start()
    started = time.monotonic()
    try:
        run(stop)
    finally:
        watchdog.cancel()
    elapsed = time.monotonic() - started

    assert elapsed < TIMEOUT, "run() did not stop on SIGTERM; the watchdog ended it"
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
        stderr = proc.stderr
        assert stderr is not None
        lines: queue.Queue[str] = queue.Queue()
        threading.Thread(target=lambda: lines.put(stderr.readline()), daemon=True).start()
        assert "worker started" in lines.get(timeout=10)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
