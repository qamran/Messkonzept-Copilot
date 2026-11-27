"""Worker entrypoint: runs the run executor until SIGTERM (MKC-17, decision 57)."""

import logging
import signal
import threading
from types import FrameType

from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings, get_settings
from mkc.db.session import get_engine
from mkc.models.client import ModelClient
from mkc.observability.langfuse import LangfuseSink
from mkc.observability.trace import Tracer
from mkc.worker.executor import Executor

log = logging.getLogger("mkc.worker")

_STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT)


def build_executor(
    settings: Settings, sessions: sessionmaker[Session], *, sink: LangfuseSink | None = None
) -> Executor:
    """The worker's executor with its tracer (MKC-19): `run_log` always, Langfuse when the
    keys are set (or `sink`, built by the caller). The model client is built only once a run
    is held."""
    tracer = Tracer(sessions, sink or LangfuseSink.from_settings(settings))
    return Executor(
        settings,
        sessions=sessions,
        client_factory=lambda: ModelClient.from_settings(settings, tracers=[tracer.span_model]),
        tracer=tracer,
    )


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
    executor = build_executor(settings, sessionmaker(bind=get_engine()))

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
        if executor.tracer is not None:
            executor.tracer.flush()  # what Langfuse still holds; bounded by its timeout
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    log.info("worker stopped")


if __name__ == "__main__":
    run()
