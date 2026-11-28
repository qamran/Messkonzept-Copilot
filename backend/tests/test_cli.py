"""MKC-20.4: `mkc run start|resume|status|inspect` (feature 26, decision 60), with Typer's
runner against the test database. The model is a scripted fake (`mkc.cli.make_client`)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, update
from sqlalchemy.orm import Session
from typer.testing import CliRunner, Result

from mkc.cli import app
from mkc.db.models import Run
from mkc.models.client import ModelClient
from mkc.worker.lease import claim_run
from tests.harness.conftest import engine, make_run, states
from tests.harness.test_baseline import READ, saved
from tests.harness.test_loop import config
from tests.models.fakes import FakeChatModel

__all__ = ["engine"]

runner = CliRunner()
E4_FILE = Path(__file__).resolve().parents[1] / "data" / "e4_faults.yaml"
ITEMS = """\
- concept_key: MK-1
  document_hash: sha256:doc
  task: {operator: Stadtwerke Musterstadt, concept_key: MK-1, region: page 3}
- concept_key: MK-2
  document_hash: sha256:doc
  task: {operator: Stadtwerke Musterstadt, concept_key: MK-2, region: page 4}
"""


@pytest.fixture
def items(tmp_path: Path) -> Path:
    path = tmp_path / "items.yaml"
    path.write_text(ITEMS, encoding="utf-8")
    return path


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeChatModel]:
    """The fake model every inline run talks to; tests set its `responses`."""
    fake = FakeChatModel(responses=[])

    def make(
        settings: Any, tracers: Any
    ) -> ModelClient:  # keeps the tracer hooks, like the real one
        return ModelClient(config(), lambda provider, name, timeout: fake, mode="live",
                           tracers=tracers)  # fmt: skip

    monkeypatch.setattr("mkc.cli.make_client", make)
    monkeypatch.setenv("MKC_WORKER_HEARTBEAT_FILE", "")
    yield fake


def mkc(*args: str) -> Result:
    return runner.invoke(app, list(args))


def run_row(engine: Engine, run_id: int) -> Run:
    with Session(engine) as session:
        run = session.get_one(Run, run_id)
        session.expunge(run)
        return run


def test_start_creates_a_queued_run(engine: Engine, items: Path) -> None:
    result = mkc("run", "start", "--items", str(items))
    assert result.exit_code == 0, result.output
    assert "run 1 created (mode full)" in result.output
    assert states(engine, 1) == ("running", ["queued", "queued"])
    assert run_row(engine, 1).mode == "full"


def test_start_takes_the_mode_from_the_setting_or_the_option(
    engine: Engine, items: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MKC_HARNESS_MODE", "baseline")
    assert mkc("run", "start", "--items", str(items)).exit_code == 0
    assert mkc("run", "start", "--items", str(items), "--mode", "full").exit_code == 0
    assert (run_row(engine, 1).mode, run_row(engine, 2).mode) == ("baseline", "full")


def test_start_refuses_a_bad_items_file(engine: Engine, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- concept_key: MK-1\n", encoding="utf-8")
    result = mkc("run", "start", "--items", str(bad))
    assert result.exit_code == 2
    assert "items file" in result.output
    with Session(engine) as session:
        assert session.query(func.count(Run.id)).scalar() == 0


def test_start_inline_runs_it(engine: Engine, items: Path, model: FakeChatModel) -> None:
    model.responses = [READ, saved(1), saved(2)]
    result = mkc("run", "start", "--items", str(items), "--inline")
    assert result.exit_code == 0, result.output
    assert "awaiting_approval" in result.output
    assert states(engine, 1) == ("awaiting_approval", ["pending_approval", "pending_approval"])
    assert run_row(engine, 1).lease_owner is None


def test_start_inline_with_a_kill_exits_137_and_resume_finishes(
    engine: Engine, items: Path, model: FakeChatModel
) -> None:
    model.responses = [saved(1), saved(2)]
    args = ("--faults", str(E4_FILE), "--plan", "kill_during_approval")
    result = mkc("run", "start", "--items", str(items), "--inline", *args)
    assert result.exit_code == 137, result.output
    assert states(engine, 1) == ("running", ["draft_saved", "queued"])
    assert run_row(engine, 1).lease_owner is None  # released, so resume can go on at once
    model.responses, model.i = [saved(2)], 0
    result = mkc("run", "resume", "1", "--inline")
    assert result.exit_code == 0, result.output
    assert states(engine, 1) == ("awaiting_approval", ["pending_approval", "pending_approval"])


def test_unknown_plan_is_refused(engine: Engine, items: Path) -> None:
    result = mkc("run", "start", "--items", str(items), "--faults", str(E4_FILE), "--plan", "x")
    assert result.exit_code == 2
    assert "no plan" in result.output


def _stopped(engine: Engine, reason: str) -> int:
    run_id, _ = make_run(engine, "queued", run_state="stopped")
    with Session(engine) as session, session.begin():
        session.execute(
            update(Run).where(Run.id == run_id).values(stop_reason=reason, started_at=func.now())
        )
    return run_id


def test_resume_restarts_a_stopped_run(engine: Engine) -> None:
    run_id = _stopped(engine, "wall_time")
    result = mkc("run", "resume", str(run_id))
    assert result.exit_code == 0, result.output
    assert "was stopped (wall_time)" in result.output
    run = run_row(engine, run_id)
    assert (run.state, run.stop_reason, run.started_at) == ("running", None, None)


def test_resume_refuses_a_done_run(engine: Engine) -> None:
    run_id, _ = make_run(engine, "failed", run_state="done")
    result = mkc("run", "resume", str(run_id))
    assert result.exit_code == 1
    assert "done" in result.output


def test_resume_after_a_cost_stop_stops_again(
    engine: Engine, items: Path, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MKC_RUN_MAX_COST_EUR", "0.0002")  # one turn costs 0.0003
    model.responses = [saved(1), saved(2)]
    mkc("run", "start", "--items", str(items), "--inline")
    assert run_row(engine, 1).stop_reason == "cost_limit"
    result = mkc("run", "resume", "1", "--inline")
    assert result.exit_code == 0, result.output
    assert "stopped (cost_limit)" in result.output
    assert len(model.seen) == 1  # the resumed run made no call


def test_inline_on_a_leased_run_refuses(engine: Engine, model: FakeChatModel) -> None:
    run_id, _ = make_run(engine, "queued")
    with Session(engine) as session, session.begin():
        assert claim_run(session, owner="worker-1", lease_seconds=60) is not None
    result = mkc("run", "resume", str(run_id), "--inline")
    assert result.exit_code == 1
    assert "leased" in result.output
    assert model.seen == []


def test_claim_run_by_id_takes_only_that_run(engine: Engine) -> None:
    first, _ = make_run(engine, "queued")
    second, _ = make_run(engine, "queued")
    with Session(engine) as session, session.begin():
        run = claim_run(session, owner="cli", lease_seconds=60, run_id=second)
        assert run is not None and run.id == second
    assert run_row(engine, first).lease_owner is None


def _done_inline(items: Path, model: FakeChatModel) -> None:
    model.responses = [READ, saved(1), saved(2)]
    assert mkc("run", "start", "--items", str(items), "--inline").exit_code == 0


def test_status_shows_state_items_usage(engine: Engine, items: Path, model: FakeChatModel) -> None:
    _done_inline(items, model)
    result = mkc("run", "status", "1")
    assert result.exit_code == 0, result.output
    for text in ("run 1: awaiting_approval (mode full)", "pending_approval 2", "steps 3",
                 "cost 0.0009 EUR", "lease: free"):  # fmt: skip
        assert text in result.output


def test_inspect_lists_items_and_log(engine: Engine, items: Path, model: FakeChatModel) -> None:
    _done_inline(items, model)
    result = mkc("run", "inspect", "1")
    assert result.exit_code == 0, result.output
    assert "MK-1" in result.output and "MK-2" in result.output
    assert "save_draft" in result.output  # from run_log
    assert "tool enqueue_approval item 1 step None: ok" in result.output  # MKC-23: traced
    detail = mkc("run", "inspect", "1", "--item", "1")
    assert "turn 1: extract_text failed" in detail.output  # the placeholder tool
    assert "turn 2: save_draft ok" in detail.output


def test_status_of_a_missing_run(engine: Engine) -> None:
    result = mkc("run", "status", "99")
    assert result.exit_code == 1
    assert "no run 99" in result.output


def test_status_of_a_baseline_run_counts_from_run_log(
    engine: Engine, items: Path, model: FakeChatModel
) -> None:
    """Baseline writes no turn rows and no start time: usage comes from `run_log`."""
    model.responses = [READ, saved(1), saved(2)]
    args = ("run", "start", "--items", str(items), "--inline", "--mode", "baseline")
    assert mkc(*args).exit_code == 0
    result = mkc("run", "status", "1")
    assert "run 1: awaiting_approval (mode baseline)" in result.output
    assert "usage (baseline, from run_log, all attempts): model calls 3, cost 0.0009 EUR" in (
        result.output
    )
    detail = mkc("run", "inspect", "1", "--item", "1")
    assert "baseline run: no turn rows" in detail.output
