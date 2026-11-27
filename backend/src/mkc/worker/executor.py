"""The run executor (MKC-17.2, decision 57): claims a run with a lease and processes it.

- `run_once` claims one run (`claim_run`), runs `process_run` on it and releases the lease.
- Two threads run while the executor is open (`with Executor(...)`): one touches the heartbeat
  file every `worker_poll_seconds`, so the liveness probe stays green during a long model call
  or a hanging database; the other renews the lease every `worker_lease_renew_seconds`. A
  renewal that finds another owner marks the lease lost; a database error does not.
- No error ends the worker: a database error goes to the outage handling, any other error is
  logged, the lease released and the worker pauses for `worker_db_backoff_max_seconds`.
- A model client that can not be built (a setup error) stops the run with `setup_error`
  (MKC-18); retries of model calls sleep on the stop flag (`wait`), so SIGTERM ends them.
- `graceful_shutdown` (SIGTERM) lets the current turn finish and commit, then the item stays
  `running`, the lease is released and `run_once` returns. The next worker resumes at once.
- A lost lease stops the run: `fence` refuses every later commit with `LeaseLost`.
- A database error is an outage only if a `SELECT 1` probe also fails. Then the worker probes
  with backoff (1, 2, 4 … `worker_db_backoff_max_seconds`), and once the database is back it
  marks the run `waiting_for_database` (the durable trace of the outage) and returns; the next
  `run_once` claims the run back to `running` and resumes from the last complete turn.
- Each run runs in its own mode (`run.mode`, MKC-20) through `execute_run`.
- Tracing (MKC-19, decision 59): with a `tracer`, each run gets its trace id before work
  starts, every stop (also a setup stop) and every outage waited out is recorded, the default
  registry reports tool calls, and the tracer is flushed after each run. The model hook is
  the client factory's (`mkc.worker.main.build_executor`).
"""

import logging
import os
import socket
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.harness.faults import FaultInjector
from mkc.harness.limits import Limits, StopReason, run_usage, stop_run
from mkc.harness.loop import SETUP_ERRORS
from mkc.harness.runner import execute_run
from mkc.harness.storage import storage_from_settings
from mkc.harness.tools import ToolRegistry
from mkc.models.client import ModelClient
from mkc.observability.trace import Tracer
from mkc.worker.lease import (
    LeaseLost,
    claim_run,
    fence,
    mark_waiting,
    release_lease,
    renew_lease,
)

__all__ = ["Executor", "claim_run", "default_owner"]

log = logging.getLogger("mkc.worker")


def default_owner() -> str:
    """`<host>-<pid>-<random>`: unique per process, readable in the `run` table."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


@dataclass
class _Held:
    """The run this executor holds, and whether its lease was lost."""

    run_id: int
    lost: threading.Event = field(default_factory=threading.Event)


class Executor:
    """One worker's run executor. Use it as a context manager (it owns a thread)."""

    def __init__(
        self,
        settings: Settings,
        *,
        sessions: sessionmaker[Session],
        client_factory: Callable[[], ModelClient],
        registry: ToolRegistry | None = None,
        owner: str | None = None,
        tracer: Tracer | None = None,
        faults: FaultInjector | None = None,
    ) -> None:
        self.settings = settings
        self.tracer = tracer
        self.faults = faults  # only the CLI and tests pass one (MKC-20, decision 60)
        # Large turn results: Supabase Storage when configured, else the `blob` table (MKC-21)
        self.blobs = storage_from_settings(settings)
        self.owner = owner or default_owner()
        self._sessions = sessions
        self._client_factory = client_factory
        self._tool_hooks = (tracer.span_tool,) if tracer is not None else ()
        self._registry = registry  # None: the default registry for each run's mode
        self._stop_hooks = (tracer.span_stop,) if tracer is not None else ()
        self._stop = threading.Event()
        self._closing = threading.Event()
        self._held: _Held | None = None
        self._lock = threading.Lock()
        self._heartbeat_file = (
            Path(settings.worker_heartbeat_file) if settings.worker_heartbeat_file else None
        )
        self._threads: list[threading.Thread] = []

    # --- lifecycle --------------------------------------------------------------------------

    def __enter__(self) -> "Executor":
        self._closing.clear()
        self._threads = [
            threading.Thread(target=self._touch_loop, name="mkc-heartbeat", daemon=True),
            threading.Thread(target=self._renew_loop, name="mkc-lease", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._closing.set()
        for thread in self._threads:
            thread.join()
        self._threads = []

    def graceful_shutdown(self) -> None:
        """Stop after the current turn; `run_once` then releases the lease and returns."""
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def wait(self, seconds: float) -> bool:
        """Sleep up to `seconds`, waking early on shutdown. True if shutdown was requested."""
        return self._stop.wait(seconds)

    # --- work -------------------------------------------------------------------------------

    def run_once(self, run_id: int | None = None) -> bool:
        """Claim one run (`run_id`, or the oldest claimable) and process it. False when there
        was no run to claim."""
        if self._stop.is_set():
            return False
        try:
            run_id = self._claim(run_id)
        except SQLAlchemyError as error:
            self._database_error(None, error)
            return False
        except Exception:
            log.exception("claim failed, backing off")
            self.wait(self.settings.worker_db_backoff_max_seconds)
            return False
        if run_id is None:
            return False
        held = _Held(run_id)
        with self._lock:
            self._held = held
        log.info("run %s claimed by %s", run_id, self.owner)
        try:
            self._process(held)
        finally:
            with self._lock:
                self._held = None
            if self.tracer is not None:
                self.tracer.flush()  # bounded by the export timeout; never raises
        return True

    def _claim(self, run_id: int | None = None) -> int | None:
        with self._sessions() as session:
            run = claim_run(
                session,
                owner=self.owner,
                lease_seconds=self.settings.worker_lease_seconds,
                run_id=run_id,
            )
            run_id = None if run is None else run.id
            session.commit()
        return run_id

    def _process(self, held: _Held) -> None:
        run_id = held.run_id
        settings = self.settings
        if self.tracer is not None:
            self.tracer.start_run(run_id)  # never raises; a resume keeps the trace id
        try:
            client = self._client_factory()
            with self._sessions() as session:
                execute_run(
                    run_id,
                    session=session,
                    sessions=self._sessions,
                    client=client,
                    registry=self._registry,
                    tool_tracers=self._tool_hooks,
                    faults=self.faults,
                    limits=Limits.from_settings(settings),
                    inline_max_bytes=settings.turn_inline_max_bytes,
                    blobs=self.blobs,
                    code_version=settings.commit,
                    should_stop=lambda: self._stop.is_set() or held.lost.is_set(),
                    fence=lambda s: fence(s, run_id, owner=self.owner),
                    tracers=self._stop_hooks,
                    sleep=self.wait,
                )
        except LeaseLost:
            log.warning("run %s: lease lost, stopping without another write", run_id)
            return
        except SETUP_ERRORS as error:  # only the client build: the loop stops the run itself
            self._stop_for_setup(run_id, error)
            return
        except SQLAlchemyError as error:
            self._database_error(run_id, error)
            return
        except Exception:
            log.exception("run %s: unexpected error, backing off", run_id)
            self._release_or_wait(run_id)
            self.wait(settings.worker_db_backoff_max_seconds)
            return
        if self._release_or_wait(run_id):
            log.info("run %s released by %s", run_id, self.owner)

    def _stop_for_setup(self, run_id: int, error: Exception) -> None:
        """The model client can not be built: stop the run with `setup_error` (MKC-18), so it
        is not claimed again every few seconds, then release the lease."""
        log.error("run %s: setup error %s, stopping the run", run_id, type(error).__name__)
        try:
            with self._sessions() as session:
                stop_run(
                    session,
                    run_id,
                    StopReason.SETUP_ERROR,
                    usage=run_usage(session, run_id),
                    fence=lambda s: fence(s, run_id, owner=self.owner),
                    tracers=self._stop_hooks,
                    detail=type(error).__name__,
                )
        except LeaseLost:
            log.warning("run %s: lease lost, stopping without another write", run_id)
            return
        except SQLAlchemyError as db_error:
            self._database_error(run_id, db_error)
            return
        self._release_or_wait(run_id)

    def _release_or_wait(self, run_id: int) -> bool:
        """Release the lease; on a database error, handle it like any other. True if released."""
        try:
            self._release(run_id)
        except SQLAlchemyError as error:
            self._database_error(run_id, error)
            return False
        return True

    def _release(self, run_id: int) -> None:
        with self._sessions() as session, session.begin():
            release_lease(session, run_id, owner=self.owner)

    # --- database outages ------------------------------------------------------------------

    def _database_up(self) -> bool:
        try:
            with self._sessions() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    def _database_error(self, run_id: int | None, error: SQLAlchemyError) -> None:
        """Wait out an outage, or log and back off when the database is reachable."""
        name = type(error).__name__
        if self._database_up():
            log.error("run %s: database error %s (the database is reachable)", run_id, name)
            if run_id is not None:
                try:
                    self._release(run_id)
                except SQLAlchemyError:
                    log.warning("run %s: lease not released; it expires", run_id)
            self.wait(self.settings.worker_db_backoff_max_seconds)
            return
        log.warning("database unavailable (%s), waiting; run %s", name, run_id)
        if not self._wait_for_database():
            log.info("shutdown while the database is unavailable; the lease expires")
            return
        log.info("database available again")
        if run_id is None:
            return
        if self.tracer is not None:
            self.tracer.outage(run_id, name)  # the durable record of the outage (MKC-19)
        try:
            with self._sessions() as session, session.begin():
                marked = mark_waiting(session, run_id, owner=self.owner)
        except SQLAlchemyError as again:
            log.warning("run %s: not marked waiting_for_database: %s", run_id, again)
            return
        if marked:
            log.info("run %s: waiting_for_database, resuming", run_id)

    def _wait_for_database(self) -> bool:
        """Probe with backoff until the database answers (True) or shutdown (False)."""
        ceiling = self.settings.worker_db_backoff_max_seconds
        delay = min(1.0, ceiling)
        while True:
            if self.wait(delay):
                return False
            if self._database_up():
                return True
            delay = min(delay * 2, ceiling)

    # --- the heartbeat and lease threads -----------------------------------------------------

    def _touch_loop(self) -> None:
        while True:
            self._touch()
            if self._closing.wait(self.settings.worker_poll_seconds):
                return

    def _renew_loop(self) -> None:
        while not self._closing.wait(self.settings.worker_lease_renew_seconds):
            self._renew()

    def _touch(self) -> None:
        """Touch the heartbeat file; a failed write is logged and shows up as a failing probe."""
        if self._heartbeat_file is None:
            return
        try:
            self._heartbeat_file.touch()
        except Exception as exc:  # no error ends this thread (MKC-17 finding 6)
            log.warning("heartbeat %s not written: %s", self._heartbeat_file, exc)

    def _renew(self) -> None:
        with self._lock:
            held = self._held
        if held is None:
            return
        try:
            with self._sessions() as session, session.begin():
                ok = renew_lease(
                    session,
                    held.run_id,
                    owner=self.owner,
                    lease_seconds=self.settings.worker_lease_seconds,
                )
        except SQLAlchemyError as error:  # not a lost lease: the database may be back soon
            log.warning("run %s: lease not renewed: %s", held.run_id, type(error).__name__)
            return
        except Exception:  # no error ends this thread (MKC-17 finding 6); retried next time
            log.exception("run %s: lease renewal failed", held.run_id)
            return
        if not ok:
            log.warning("run %s: lease taken over by another worker", held.run_id)
            held.lost.set()
