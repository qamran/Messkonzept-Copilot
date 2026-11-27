"""The run executor (MKC-17.2, decision 57): claims a run with a lease and processes it.

- `run_once` claims one run (`claim_run`), runs `process_run` on it and releases the lease.
- A heartbeat thread runs while the executor is open (`with Executor(...)`): it touches the
  heartbeat file every `worker_poll_seconds`, so the liveness probe stays green during a long
  model call, and renews the lease every `worker_lease_renew_seconds`. A renewal that finds
  another owner marks the lease lost; a renewal that fails with a database error does not.
- `graceful_shutdown` (SIGTERM) lets the current turn finish and commit, then the item stays
  `running`, the lease is released and `run_once` returns. The next worker resumes at once.
- A lost lease stops the run: `fence` refuses every later commit with `LeaseLost`.
- A database error is an outage only if a `SELECT 1` probe also fails. Then the worker probes
  with backoff (1, 2, 4 … `worker_db_backoff_max_seconds`), and once the database is back it
  marks the run `waiting_for_database` (the durable trace of the outage) and returns; the next
  `run_once` claims the run back to `running` and resumes from the last complete turn.
"""

import logging
import os
import socket
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.harness.loop import SETUP_ERRORS, process_run
from mkc.harness.registry import default_registry
from mkc.harness.tools import ToolRegistry
from mkc.models.client import ModelClient
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
    ) -> None:
        self.settings = settings
        self.owner = owner or default_owner()
        self._sessions = sessions
        self._client_factory = client_factory
        self._registry = registry or default_registry(sessions=sessions)
        self._stop = threading.Event()
        self._closing = threading.Event()
        self._held: _Held | None = None
        self._lock = threading.Lock()
        self._heartbeat_file = (
            Path(settings.worker_heartbeat_file) if settings.worker_heartbeat_file else None
        )
        self._thread: threading.Thread | None = None

    # --- lifecycle --------------------------------------------------------------------------

    def __enter__(self) -> "Executor":
        self._closing.clear()
        self._thread = threading.Thread(target=self._heartbeat, name="mkc-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._closing.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

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

    def run_once(self) -> bool:
        """Claim one run and process it. False when there was no run to claim."""
        if self._stop.is_set():
            return False
        try:
            run_id = self._claim()
        except SQLAlchemyError as error:
            self._database_error(None, error)
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
        return True

    def _claim(self) -> int | None:
        with self._sessions() as session:
            run = claim_run(
                session, owner=self.owner, lease_seconds=self.settings.worker_lease_seconds
            )
            run_id = None if run is None else run.id
            session.commit()
        return run_id

    def _process(self, held: _Held) -> None:
        run_id = held.run_id
        settings = self.settings
        try:
            with self._sessions() as session:
                process_run(
                    run_id,
                    session=session,
                    client=self._client_factory(),
                    registry=self._registry,
                    max_steps=settings.item_max_steps,
                    inline_max_bytes=settings.turn_inline_max_bytes,
                    code_version=settings.commit,
                    should_stop=lambda: self._stop.is_set() or held.lost.is_set(),
                    fence=lambda s: fence(s, run_id, owner=self.owner),
                )
        except LeaseLost:
            log.warning("run %s: lease lost, stopping without another write", run_id)
            return
        except SETUP_ERRORS as error:
            log.error("run %s: setup error %s, backing off", run_id, type(error).__name__)
            self._release(run_id)
            self.wait(settings.worker_db_backoff_max_seconds)
            return
        except SQLAlchemyError as error:
            self._database_error(run_id, error)
            return
        self._release(run_id)
        log.info("run %s released by %s", run_id, self.owner)

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

    # --- heartbeat thread -------------------------------------------------------------------

    def _heartbeat(self) -> None:
        last_renewal = time.monotonic()
        while True:
            self._touch()
            if time.monotonic() - last_renewal >= self.settings.worker_lease_renew_seconds:
                last_renewal = time.monotonic()
                self._renew()
            if self._closing.wait(self.settings.worker_poll_seconds):
                return

    def _touch(self) -> None:
        """Touch the heartbeat file; a failed write is logged and shows up as a failing probe."""
        if self._heartbeat_file is None:
            return
        try:
            self._heartbeat_file.touch()
        except OSError as exc:
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
        if not ok:
            log.warning("run %s: lease taken over by another worker", held.run_id)
            held.lost.set()
