"""MKC-20.2: the executor runs each run in the mode it was created with (decision 60)."""

from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from mkc.db.models import Run, Turn
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import SAVE
from tests.models.fakes import FakeChatModel, ai
from tests.worker.test_executor import executor, read


def test_executor_runs_each_run_in_its_mode(engine: Engine) -> None:
    baseline, _ = make_run(engine, "queued")
    with Session(engine) as session, session.begin():
        session.execute(update(Run).where(Run.id == baseline).values(mode="baseline"))
    model = FakeChatModel(responses=[read(1), ai(tool_calls=[SAVE])])
    with executor(engine, model, "w1") as worker:
        assert worker.run_once() is True
    assert states(engine, baseline) == ("awaiting_approval", ["draft_saved"])
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Turn)) == 0
