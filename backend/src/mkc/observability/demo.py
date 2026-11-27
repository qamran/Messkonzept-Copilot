"""One real traced run (MKC-19.5): `uv run python -m mkc.observability.demo`.

Makes one synthetic run with one item (the fictional operator "Stadtwerke Musterstadt"; no
real document), runs it once through the worker's own executor and prints the run id, its
state and its trace id. Needs `MKC_MODEL_MODE=live` (it spends a few cents at most: keep
`MKC_ITEM_MAX_STEPS` and `MKC_RUN_MAX_COST_EUR` small) and a local database: it refuses a
`DATABASE_URL` that is not on this machine.
"""

import sys
import time
from collections import Counter

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.db.models import Item, Run, RunLog
from mkc.harness.states import ItemState, RunState
from mkc.observability.langfuse import LangfuseSink

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

TASK = {
    "operator": "Stadtwerke Musterstadt",
    "concept_key": "MK-DEMO-1",
    "region": "page 1",
    "note": "synthetic tracing demo (MKC-19.5): there is no document to read",
}


def make_demo_run(session: Session) -> int:
    """A `running` run with one `queued` synthetic item. The caller commits."""
    run = Run(state=RunState.RUNNING.value)
    session.add(run)
    session.flush()
    session.add(
        Item(
            run_id=run.id,
            concept_key=TASK["concept_key"],
            document_hash="sha256:demo",
            task=dict(TASK),
            state=ItemState.QUEUED.value,
        )
    )
    session.flush()
    return run.id


LANGFUSE_TYPES = {"model": "GENERATION", "tool": "TOOL", "stop": "EVENT", "outage": "EVENT"}
"""The Langfuse observation type of each `run_log` kind."""


def expected_types(kinds: list[str]) -> Counter[str]:
    """The Langfuse observation types a run's `run_log` kinds should arrive as."""
    return Counter(LANGFUSE_TYPES[kind] for kind in kinds)


def main() -> int:
    settings = Settings()
    if settings.model_mode != "live":
        print("the demo needs MKC_MODEL_MODE=live (it makes real model calls)", file=sys.stderr)
        return 2
    if make_url(settings.database_url).host not in LOCAL_HOSTS:
        print("the demo writes a run: point DATABASE_URL at a local database", file=sys.stderr)
        return 2
    sink = LangfuseSink.from_settings(settings)
    if sink is None:
        print("the demo needs the Langfuse keys (MKC_LANGFUSE_*)", file=sys.stderr)
        return 2
    if not sink.auth_check():
        print(
            "Langfuse refused the keys: check the keys and MKC_LANGFUSE_BASE_URL", file=sys.stderr
        )
        return 2
    from mkc.worker.main import build_executor  # the worker's own wiring

    engine = create_engine(settings.database_url)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        run_id = make_demo_run(session)
        session.commit()
    with build_executor(settings, sessions, sink=sink) as executor:
        executor.run_once()
    with sessions() as session:
        run = session.get_one(Run, run_id)
        kinds = list(session.scalars(select(RunLog.kind).where(RunLog.run_id == run_id)))
        print(f"run {run_id}: {run.state} {run.stop_reason or ''}".rstrip())
        print(f"trace id: {run.trace_id}")
    engine.dispose()
    if run.trace_id is None:
        print("no trace id: the executor claimed another run first", file=sys.stderr)
        return 1
    return _read_back(sink, run.trace_id, expected_types(kinds))


def _read_back(sink: LangfuseSink, trace_id: str, expected: Counter[str]) -> int:
    """Wait for Langfuse to store the trace (ingestion is asynchronous), then compare."""
    found: list[tuple[str, bool]] = []
    for _ in range(20):
        found = sink.observations(trace_id)
        if Counter(kind for kind, _ in found) == expected:
            break
        time.sleep(3)
    got = Counter(kind for kind, _ in found)
    print(f"run_log expects {dict(expected)}; Langfuse has {dict(got)}")
    print(f"observations with input or output: {sum(content for _, content in found)}")
    return 0 if got == expected and not any(content for _, content in found) else 1


if __name__ == "__main__":
    raise SystemExit(main())
