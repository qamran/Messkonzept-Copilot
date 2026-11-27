"""MKC-4.2: the worker starts and exits cleanly on SIGTERM, also without a database.
MKC-17.4: it runs the executor on the runs in the database."""

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from mkc.db.models import Run
from mkc.worker.main import run
from tests.harness.conftest import make_run

TIMEOUT = 10.0  # a refused connect can take 2 s on Windows, twice


def test_run_stops_on_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    previous = signal.getsignal(signal.SIGTERM)
    stop = threading.Event()
    timed_out = threading.Event()

    def end_run() -> None:  # ends run() if SIGTERM is ignored
        timed_out.set()
        stop.set()

    sigterm = threading.Timer(0.2, signal.raise_signal, args=(signal.SIGTERM,))
    watchdog = threading.Timer(TIMEOUT, end_run)

    sigterm.start()
    watchdog.start()
    try:
        run(stop)
    finally:
        # Cancel both: if run() fails early, a pending SIGTERM would hit pytest itself.
        sigterm.cancel()
        watchdog.cancel()

    assert not timed_out.is_set(), "run() did not stop on SIGTERM; the watchdog ended it"
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


def test_worker_runs_the_executor(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run with no items is claimed, settled `done` and released by `run()`."""
    monkeypatch.setenv("MKC_WORKER_POLL_SECONDS", "0.05")
    monkeypatch.setenv("MKC_MODEL_REPLAY_DIR", str(tmp_path))
    run_id, _ = make_run(engine)
    stop = threading.Event()

    def stop_when_done() -> None:
        for _ in range(int(TIMEOUT / 0.05)):
            with Session(engine) as session:
                if session.get_one(Run, run_id).state == "done":
                    break
            time.sleep(0.05)
        stop.set()

    watcher = threading.Thread(target=stop_when_done, daemon=True)
    watcher.start()
    run(stop)
    watcher.join()
    with Session(engine) as session:
        done = session.get_one(Run, run_id)
        assert (done.state, done.lease_owner) == ("done", None)
