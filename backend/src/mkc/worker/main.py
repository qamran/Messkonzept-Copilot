"""Worker entrypoint. Later tickets add the harness queue to the poll loop."""

import logging
import signal
import threading
from types import FrameType

from mkc.config import get_settings

log = logging.getLogger("mkc.worker")

_STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT)


def run() -> None:
    """Poll for work until SIGTERM or SIGINT, then return cleanly.

    Must be called from the main thread (Python only installs signal handlers there).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    stop = threading.Event()

    def request_stop(signum: int, _frame: FrameType | None) -> None:
        log.info("signal %s received, stopping", signal.Signals(signum).name)
        stop.set()

    previous = {sig: signal.signal(sig, request_stop) for sig in _STOP_SIGNALS}
    try:
        log.info("worker started")
        while not stop.wait(settings.worker_poll_seconds):
            pass  # the harness queue is polled here (MKC-17 and later)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    log.info("worker stopped")


if __name__ == "__main__":
    run()
