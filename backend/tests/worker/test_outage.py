"""MKC-17.3: the worker waits out a database outage and resumes without losing state
(decision 57, Review Focus 4). The test cuts the test database for real, then restores it."""

import threading
import time
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from mkc.worker.executor import Executor
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import SAVE, Tools, client_for
from tests.models.fakes import ai
from tests.worker.test_executor import HookModel, read, settings, turn_numbers

HISTORY = """
CREATE TABLE IF NOT EXISTS run_state_log (id serial PRIMARY KEY, run_id bigint, state text);
CREATE OR REPLACE FUNCTION log_run_state() RETURNS trigger AS $$
BEGIN
  IF NEW.state IS DISTINCT FROM OLD.state THEN
    INSERT INTO run_state_log (run_id, state) VALUES (NEW.id, NEW.state);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE OR REPLACE TRIGGER run_state_history AFTER UPDATE ON run
  FOR EACH ROW EXECUTE FUNCTION log_run_state();
"""


@pytest.fixture
def history(engine: Engine) -> Iterator[None]:
    """A test-only trigger that records every run state change."""
    with engine.begin() as conn:
        conn.execute(text(HISTORY))
    yield
    engine.dispose()  # its pooled connections died in the outage
    with engine.begin() as conn:
        conn.execute(text("DROP TRIGGER run_state_history ON run; DROP TABLE run_state_log"))


class Outage:
    """Cuts every connection to the test database and refuses new ones until `restore`."""

    def __init__(self, url: URL) -> None:
        self.name = url.database
        self.admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")

    def cut(self) -> None:
        with self.admin.connect() as conn:
            conn.execute(text(f'ALTER DATABASE "{self.name}" ALLOW_CONNECTIONS false'))
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": self.name},
            )

    def restore(self) -> None:
        with self.admin.connect() as conn:
            conn.execute(text(f'ALTER DATABASE "{self.name}" ALLOW_CONNECTIONS true'))


def run_history(engine: Engine, run_id: int) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT state FROM run_state_log WHERE run_id = :id ORDER BY id"), {"id": run_id}
        )
        return [row.state for row in rows]


def test_database_unavailable_sets_waiting_and_resumes(
    engine: Engine, history: None, database_env: URL
) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    outage = Outage(database_env)
    restored = threading.Event()

    def cut_then_restore() -> None:  # during model call 2: the database goes away for 1 s
        outage.cut()

        def back() -> None:
            outage.restore()
            restored.set()

        threading.Timer(1.0, back).start()

    model = HookModel(
        responses=[read(1), read(2), read(2), ai(tool_calls=[SAVE])],
        hooks={2: cut_then_restore},
    )
    worker_engine = create_engine(database_env, pool_pre_ping=True)
    worker = Executor(
        settings(worker_db_backoff_max_seconds=0.2),
        sessions=sessionmaker(bind=worker_engine),
        client_factory=lambda: client_for(model),
        registry=Tools().registry(),
        owner="w1",
    )
    try:
        with worker:
            assert worker.run_once() is True  # turn 2 could not be stored: waits, marks
            assert restored.is_set()
            assert worker.run_once() is True  # claims the run again and resumes
    finally:
        outage.restore()
        worker_engine.dispose()
    engine.dispose()
    assert len(model.seen) == 4  # the turn in flight was asked again, nothing else
    assert turn_numbers(engine, item_id) == [1, 2, 3]  # turn 1 kept, no gap
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])
    assert run_history(engine, run_id) == [
        "waiting_for_database",
        "running",
        "awaiting_approval",
    ]


def test_shutdown_ends_the_wait_for_an_unreachable_database() -> None:
    """No database at all (as in the kind and Compose smoke tests): the worker waits and
    still stops at once on SIGTERM."""
    nowhere = create_engine(
        "postgresql+psycopg://mkc:mkc@127.0.0.1:1/mkc", connect_args={"connect_timeout": 2}
    )
    worker = Executor(
        settings(worker_db_backoff_max_seconds=0.2),
        sessions=sessionmaker(bind=nowhere),
        client_factory=lambda: pytest.fail("no client without a run"),
        registry=Tools().registry(),
        owner="w1",
    )
    threading.Timer(0.5, worker.graceful_shutdown).start()
    started = time.monotonic()
    with worker:
        assert worker.run_once() is False
    # A refused connect returns at once on Linux; Windows retries it for up to the 2 s connect
    # timeout, once for the claim and once for the probe. Without the stop it would go on.
    assert time.monotonic() - started < 2 * 2 + 1.5
