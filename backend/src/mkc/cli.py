"""The run CLI: `mkc run start|resume|status|inspect` (MKC-20.4, feature 26, decision 60).

- `start` creates a run (`running`, in its mode) and its `queued` items from a synthetic
  items file (until MKC-21 fetches and segments real documents). The worker picks it up;
  with `--inline` the CLI claims that run with a lease and processes it here.
- `resume` brings a `stopped` run back to `running` (stop reason and wall clock cleared;
  steps and cost keep counting from the stored turns).
- `status` and `inspect` read the run, its items, turns and `run_log`.
- Fault plans (`--faults FILE --plan NAME`) only come in here, never from a setting. An
  injected kill exits with 137 after the lease is released, so `resume` can go on at once.

Exit codes: 0 done, 1 refused (no such run, wrong state, leased elsewhere), 2 bad input,
137 killed by a fault plan.
"""

from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings, get_settings
from mkc.db.models import Item, Run, RunLog, Turn
from mkc.db.session import get_engine
from mkc.harness.faults import FaultInjector, InjectedKill, load_fault_plans
from mkc.harness.limits import run_usage
from mkc.harness.mode import HarnessMode
from mkc.harness.states import ItemState, RunState, transition
from mkc.models.client import ModelClient
from mkc.worker.executor import default_owner
from mkc.worker.lease import release_lease
from mkc.worker.main import build_executor

app = typer.Typer(no_args_is_help=True, help="Messkonzept-Copilot command line.")
run_app = typer.Typer(no_args_is_help=True, help="Start, resume and inspect runs.")
app.add_typer(run_app, name="run")

KILLED = 137


def make_client(settings: Settings, tracers: Sequence[Any]) -> ModelClient:
    """The model client of an inline run (tests replace it with a fake)."""
    return ModelClient.from_settings(settings, tracers=tracers)


class ItemSpec(BaseModel):
    """One line of the items file: what an item is told and keyed by."""

    model_config = ConfigDict(extra="forbid")

    concept_key: str = Field(min_length=1)
    document_hash: str = Field(min_length=1)
    task: dict[str, Any]


_ITEMS = TypeAdapter(list[ItemSpec])

ItemsOpt = Annotated[Path, typer.Option("--items", help="YAML list of items.")]
ModeOpt = Annotated[HarnessMode | None, typer.Option(help="Default: MKC_HARNESS_MODE.")]
InlineOpt = Annotated[bool, typer.Option("--inline", help="Process the run here.")]
FaultsOpt = Annotated[Path | None, typer.Option("--faults", help="YAML fault plans (E4).")]
PlanOpt = Annotated[str | None, typer.Option("--plan", help="The plan's name in --faults.")]


def _fail(message: str, code: int) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code)


def _sessions() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine())


def _injector(faults: Path | None, plan: str | None) -> FaultInjector | None:
    if faults is None and plan is None:
        return None
    if faults is None or plan is None:
        raise _fail("--faults and --plan go together", 2)
    try:
        plans = load_fault_plans(faults)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise _fail(f"fault file {faults}: {error}", 2) from error
    if plan not in plans:
        raise _fail(f"no plan {plan!r} in {faults} (plans: {', '.join(sorted(plans))})", 2)
    return FaultInjector(plans[plan])


def _read_items(path: Path) -> list[ItemSpec]:
    try:
        return _ITEMS.validate_python(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise _fail(f"items file {path}: {error}", 2) from error


def _process(settings: Settings, run_id: int, faults: FaultInjector | None) -> None:
    """Claim `run_id` with this process's lease and run it here; report how it ended."""
    settings = settings.model_copy(update={"worker_heartbeat_file": ""})  # not the worker's
    sessions = _sessions()
    executor = build_executor(
        settings, sessions, make_client=make_client, owner=f"cli-{default_owner()}",
        faults=faults,
    )  # fmt: skip
    try:
        with executor:
            claimed = executor.run_once(run_id)
    except InjectedKill as kill:
        with sessions.begin() as session:
            release_lease(session, run_id, owner=executor.owner)
        raise _fail(
            f"run {run_id}: {kill}; resume with `mkc run resume {run_id}`", KILLED
        ) from kill
    if not claimed:
        raise _fail(f"run {run_id} is leased by another worker or not claimable", 1)
    with sessions() as session:
        run = session.get_one(Run, run_id)
        reason = f" ({run.stop_reason})" if run.stop_reason else ""
        typer.echo(f"run {run_id}: {run.state}{reason}")


@run_app.command()
def start(
    items: ItemsOpt,
    mode: ModeOpt = None,
    inline: InlineOpt = False,
    faults: FaultsOpt = None,
    plan: PlanOpt = None,
) -> None:
    """Create a run with one queued item per entry of the items file."""
    settings = get_settings()
    specs = _read_items(items)
    injector = _injector(faults, plan)
    mode = mode or settings.harness_mode
    with _sessions().begin() as session:
        run = Run(state=RunState.RUNNING.value, mode=mode.value)
        session.add(run)
        session.flush()
        session.add_all(
            Item(run_id=run.id, concept_key=s.concept_key, document_hash=s.document_hash,
                 task=s.task, state=ItemState.QUEUED.value)
            for s in specs
        )  # fmt: skip
        run_id = run.id
    typer.echo(f"run {run_id} created (mode {mode.value}): {len(specs)} items")
    if inline:
        _process(settings, run_id, injector)


@run_app.command()
def resume(
    run_id: int, inline: InlineOpt = False, faults: FaultsOpt = None, plan: PlanOpt = None
) -> None:
    """Bring a stopped run back to running; with --inline, process it here."""
    injector = _injector(faults, plan)
    with _sessions().begin() as session:
        run = session.scalars(select(Run).where(Run.id == run_id).with_for_update()).first()
        if run is None:
            raise _fail(f"no run {run_id}", 1)
        state = RunState(run.state)
        if state is RunState.STOPPED:
            typer.echo(f"run {run_id} was stopped ({run.stop_reason}); resuming")
            run.state = transition(state, RunState.RUNNING).value
            run.stop_reason = None
            run.started_at = None  # the wall-time limit counts from this resume
        elif state not in (RunState.RUNNING, RunState.WAITING_FOR_DATABASE):
            raise _fail(f"run {run_id} is {state.value}; nothing to resume", 1)
    if inline:
        _process(get_settings(), run_id, injector)


@run_app.command()
def status(run_id: int) -> None:
    """State, mode, items per state, usage and lease of a run."""
    with _sessions()() as session:
        run = _run(session, run_id)
        counts = Counter(session.scalars(select(Item.state).where(Item.run_id == run_id)))
        lease = f"{run.lease_owner} until {run.lease_expires_at}" if run.lease_owner else "free"
        typer.echo(f"run {run_id}: {run.state} (mode {run.mode})")
        typer.echo(f"stop reason: {run.stop_reason or '-'}")
        typer.echo("items: " + (", ".join(f"{s} {n}" for s, n in sorted(counts.items())) or "-"))
        if run.mode == HarnessMode.BASELINE:  # no turn rows, no start time: read run_log
            calls, cost = session.execute(
                select(func.count(RunLog.id), func.coalesce(func.sum(RunLog.cost_eur), 0)).where(
                    RunLog.run_id == run_id, RunLog.kind == "model"
                )
            ).one()
            typer.echo(f"usage (baseline, from run_log, all attempts): model calls {calls}, "
                       f"cost {Decimal(cost or 0):.4f} EUR")  # fmt: skip
        else:
            usage = run_usage(session, run_id)
            typer.echo(f"usage: steps {usage.steps}, cost {usage.cost_eur:.4f} EUR, "
                       f"wall {usage.wall_s:.1f} s")  # fmt: skip
        typer.echo(f"lease: {lease}")


@run_app.command()
def inspect(
    run_id: int, item: Annotated[int | None, typer.Option(help="Show one item's turns.")] = None
) -> None:
    """Items with their turns and cost, the latest run_log rows, or one item's turns."""
    with _sessions()() as session:
        _run(session, run_id)
        if item is not None:
            _item_turns(session, run_id, item)
            return
        rows = session.execute(
            select(Item, func.count(Turn.id), func.coalesce(func.sum(Turn.cost_eur), 0))
            .outerjoin(Turn, Turn.item_id == Item.id)
            .where(Item.run_id == run_id)
            .group_by(Item.id)
            .order_by(Item.id)
        ).all()
        for it, turns, cost in rows:
            reason = f" ({it.failure_reason})" if it.failure_reason else ""
            typer.echo(f"item {it.id} {it.concept_key}: {it.state}{reason}, "
                       f"{turns} turns, {Decimal(cost):.4f} EUR")  # fmt: skip
        logs = session.scalars(
            select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.id.desc()).limit(20)
        ).all()
        typer.echo("run_log (latest 20):")
        for log in reversed(logs):
            ok = "ok" if log.ok else f"failed: {log.error or '-'}"
            typer.echo(f"  {log.kind} {log.name} item {log.item_id} step {log.step}: {ok}")


def _run(session: Session, run_id: int) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise _fail(f"no run {run_id}", 1)
    return run


def _item_turns(session: Session, run_id: int, item_id: int) -> None:
    it = session.get(Item, item_id)
    if it is None or it.run_id != run_id:
        raise _fail(f"no item {item_id} in run {run_id}", 1)
    typer.echo(f"item {it.id} {it.concept_key}: {it.state}")
    run = session.get_one(Run, run_id)
    if run.mode == HarnessMode.BASELINE:
        typer.echo("baseline run: no turn rows (checkpoints off); see run_log in `inspect`")
        return
    turns = session.scalars(select(Turn).where(Turn.item_id == item_id).order_by(Turn.number))
    for turn in turns:
        calls = [f"{r['name']} {'ok' if _ok(r) else 'failed'}" for r in turn.tool_results]
        calls = calls or ["no tool call"]
        typer.echo(f"turn {turn.number}: {', '.join(calls)} ({turn.cost_eur} EUR)")


def _ok(entry: dict[str, Any]) -> bool:
    """A stored result is inline (`result`) or a blob ref (`result_ref`); both carry `ok`."""
    return bool((entry.get("result") or entry.get("result_ref") or {}).get("ok"))
