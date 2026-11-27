"""Worker entrypoint: runs the run executor until SIGTERM (MKC-17, decision 57)."""

import logging
import signal
import threading
from types import FrameType

from sqlalchemy.orm import sessionmaker

from mkc.config import get_settings
from mkc.db.session import get_engine
from mkc.models.client import ModelClient
from mkc.worker.executor import Executor

log = logging.getLogger("mkc.worker")

_STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT)


def run(stop: threading.Event | None = None) -> None:
    """Claim and process runs until SIGTERM or SIGINT (or `stop` is set), then return cleanly.

    Two executor threads run meanwhile: one touches the heartbeat file, one renews the lease.
    On a stop, the current turn finishes and commits, the lease is released, and `run` returns.
    Must be called from the main thread (Python only installs signal handlers there).
    `stop` lets a caller, such as a test watchdog, end the loop from another thread.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    stop = stop or threading.Event()
    executor = Executor(
        settings,
        sessions=sessionmaker(bind=get_engine()),
        client_factory=lambda: ModelClient.from_settings(settings),  # only once a run is held
    )

    def request_stop(signum: int, _frame: FrameType | None) -> None:
        log.info("signal %s received, stopping", signal.Signals(signum).name)
        stop.set()

    def forward_stop() -> None:  # a set `stop` ends the turn, a backoff or a poll wait
        stop.wait()
        executor.graceful_shutdown()

    previous = {sig: signal.signal(sig, request_stop) for sig in _STOP_SIGNALS}
    threading.Thread(target=forward_stop, name="mkc-stop", daemon=True).start()
    try:
        log.info("worker started as %s", executor.owner)
        with executor:
            while not stop.is_set():
                if not executor.run_once():
                    executor.wait(settings.worker_poll_seconds)
    finally:
        stop.set()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    log.info("worker stopped")


if __name__ == "__main__":
    run()
