"""MKC-17.2: the executor finishes the turn on shutdown, releases the lease, keeps the
heartbeat file and the lease fresh, and stops writing once the lease is lost (decision 57)."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import Field
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.db.models import Run, Turn
from mkc.worker.executor import Executor
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import SAVE, Tools, call, client_for
from tests.models.fakes import FakeChatModel, ai


class HookModel(FakeChatModel):
    """Runs `hooks[n]` at the start of model call n (1-based), then replies as scripted."""

    hooks: dict[int, Callable[[], None]] = Field(default_factory=dict)

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        hook = self.hooks.get(len(self.seen) + 1)
        if hook is not None:
            hook()
        return super()._generate(messages, *args, **kwargs)


def read(page: int) -> AIMessage:
    return ai(tool_calls=[call("extract_text", f"r{page}", page=page)])


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "worker_poll_seconds": 0.05,
        "worker_lease_seconds": 60.0,
        "worker_lease_renew_seconds": 5.0,
        "item_max_steps": 6,
    }
    return Settings(**{**values, **overrides})


def executor(engine: Engine, model: FakeChatModel, owner: str, **overrides: Any) -> Executor:
    return Executor(
        settings(**overrides),
        sessions=sessionmaker(bind=engine),
        client_factory=lambda: client_for(model),
        registry=Tools().registry(),
        owner=owner,
    )


def turn_numbers(engine: Engine, item_id: int) -> list[int]:
    with Session(engine) as session:
        rows = session.scalars(select(Turn.number).where(Turn.item_id == item_id))
        return sorted(rows)


def owner_of(engine: Engine, run_id: int) -> str | None:
    with Session(engine) as session:
        return session.get_one(Run, run_id).lease_owner


def test_sigterm_finishes_turn_then_releases_lease(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    model = HookModel(responses=[read(1), read(2), ai(tool_calls=[SAVE])])
    first = executor(engine, model, "w1")
    model.hooks = {2: first.graceful_shutdown}  # SIGTERM arrives during model call 2
    with first:
        assert first.run_once() is True
    assert len(model.seen) == 2  # no model call after the shutdown
    assert turn_numbers(engine, item_id) == [1, 2]  # the turn in flight was finished
    assert states(engine, run_id) == ("running", ["running"])
    assert owner_of(engine, run_id) is None  # the lease is released

    second_model = HookModel(responses=[ai(tool_calls=[SAVE])])
    with executor(engine, second_model, "w2") as second:
        assert second.run_once() is True
    assert turn_numbers(engine, item_id) == [1, 2, 3]
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])
    assert owner_of(engine, run_id) is None


def test_run_once_without_a_run_returns_false(engine: Engine) -> None:
    with executor(engine, HookModel(responses=[]), "w1") as idle:
        assert idle.run_once() is False


def test_heartbeat_and_lease_stay_fresh_during_a_slow_model_call(
    engine: Engine, tmp_path: Path
) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    heartbeat = tmp_path / "beat"
    seen: dict[str, Any] = {}

    def slow() -> None:  # longer than the lease and the probe's max age
        time.sleep(1.5)
        seen["file_age"] = time.time() - heartbeat.stat().st_mtime
        with Session(engine) as session:
            valid = select(Run.lease_expires_at > func.now()).where(Run.id == run_id)
            seen["lease_valid"] = session.scalar(valid)

    model = HookModel(responses=[ai(tool_calls=[SAVE])], hooks={1: slow})
    with executor(
        engine,
        model,
        "w1",
        worker_heartbeat_file=str(heartbeat),
        worker_lease_seconds=0.9,
        worker_lease_renew_seconds=0.2,
    ) as slow_worker:
        assert slow_worker.run_once() is True
    assert seen["file_age"] < 0.5
    assert seen["lease_valid"] is True
    assert turn_numbers(engine, item_id) == [1]  # the fence let the turn through
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved"])


def test_a_lost_lease_stores_no_further_turn(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "queued")

    def take_over() -> None:  # another worker took the run (its lease expired)
        with Session(engine) as session, session.begin():
            session.execute(update(Run).where(Run.id == run_id).values(lease_owner="w2"))

    model = HookModel(responses=[read(1), ai(tool_calls=[SAVE])], hooks={1: take_over})
    with executor(engine, model, "w1") as loser:
        assert loser.run_once() is True
    assert len(model.seen) == 1
    assert turn_numbers(engine, item_id) == []
    assert states(engine, run_id) == ("running", ["running"])
    assert owner_of(engine, run_id) == "w2"  # not released by the loser
