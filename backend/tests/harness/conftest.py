"""DB helpers for the harness tests: an engine on the migrated test database, emptied first."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from mkc.db.models import Item, Run

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture
def engine(database_env: URL) -> Iterator[Engine]:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    eng = create_engine(database_env)
    with eng.begin() as conn:
        conn.execute(text("truncate run_log, turn, item, run restart identity cascade"))
    try:
        yield eng
    finally:
        eng.dispose()


def make_run(
    engine: Engine, *item_states: str, run_state: str = "running"
) -> tuple[int, list[int]]:
    """A run with one item per given state, inserted in that order. Returns the ids."""
    with Session(engine) as session, session.begin():
        run = Run(state=run_state)
        session.add(run)
        session.flush()
        items = [
            Item(
                run_id=run.id,
                concept_key=f"MK-{n}",
                document_hash="sha256:doc",
                task=task(n),
                state=state,
            )
            for n, state in enumerate(item_states, start=1)
        ]
        session.add_all(items)
        session.flush()
        return run.id, [i.id for i in items]


def task(n: int) -> dict[str, Any]:
    return {"operator": "Stadtwerke Musterstadt", "concept_key": f"MK-{n}", "region": "page 3"}


def states(engine: Engine, run_id: int) -> tuple[str, list[str]]:
    """The run's state and its items' states in id order."""
    with Session(engine) as session:
        run = session.get_one(Run, run_id)
        items = session.query(Item).filter_by(run_id=run_id).order_by(Item.id).all()
        return run.state, [i.state for i in items]
