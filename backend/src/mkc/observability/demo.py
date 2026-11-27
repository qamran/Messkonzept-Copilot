"""One real traced run (MKC-19.5): `uv run python -m mkc.observability.demo`.

Makes one synthetic run with one item (the fictional operator "Stadtwerke Musterstadt"; no
real document), runs it once through the worker's own executor and prints the run id, its
state and its trace id. Needs `MKC_MODEL_MODE=live` (it spends a few cents at most: keep
`MKC_ITEM_MAX_STEPS` and `MKC_RUN_MAX_COST_EUR` small) and a local database: it refuses a
`DATABASE_URL` that is not on this machine.
"""

import sys
from collections import Counter

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.db.models import Item, Run
from mkc.harness.states import ItemState, RunState

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
    return Counter()


def main() -> int:
    settings = Settings()
    if settings.model_mode != "live":
        print("the demo needs MKC_MODEL_MODE=live (it makes real model calls)", file=sys.stderr)
        return 2
    if make_url(settings.database_url).host not in LOCAL_HOSTS:
        print("the demo writes a run: point DATABASE_URL at a local database", file=sys.stderr)
        return 2
    from mkc.worker.main import build_executor  # the worker's own wiring

    engine = create_engine(settings.database_url)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        run_id = make_demo_run(session)
        session.commit()
    executor = build_executor(settings, sessions)
    with executor:
        executor.run_once()
    with sessions() as session:
        run = session.get_one(Run, run_id)
        print(f"run {run_id}: {run.state} {run.stop_reason or ''}".rstrip())
        print(f"trace id: {run.trace_id}")
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
