"""MKC-20.2: baseline is the same loop with the five switches off (design 8.5, decision 60).

No checkpoints, no tool cache, no durable queue (claims and end states stay in memory until
the run ends), and approvals in memory only.
"""

from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Draft, Run, Turn
from mkc.harness.baseline import RunMemory
from mkc.harness.faults import FaultInjector, FaultPlan
from mkc.harness.limits import Limits
from mkc.harness.runner import RunResult, execute_run
from mkc.harness.tools import Tool, ToolRegistry, ToolTrace
from tests.extraction.drafts import valid_draft
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import PageArgs, Tools, call, client_for
from tests.harness.test_resume import Crash, crashing
from tests.models.fakes import FakeChatModel, ai

READ = ai(tool_calls=[call("extract_text", "r1", page=3)])


def saved(n: int) -> Any:
    """A reply that saves draft `n` (a `MesskonzeptDraft` titled `draft <n>` since MKC-23)."""
    return ai(tool_calls=[call("save_draft", f"s{n}", draft=valid_draft(f"draft {n}"))])


def titles(approvals: list[dict[str, Any]]) -> list[str]:
    return [a["body"]["title"] for a in approvals]


def make(engine: Engine, n_items: int, mode: str = "baseline") -> tuple[int, list[int]]:
    run_id, ids = make_run(engine, *["queued"] * n_items)
    with Session(engine) as session, session.begin():
        session.execute(update(Run).where(Run.id == run_id).values(mode=mode))
    return run_id, ids


def go(
    engine: Engine,
    run_id: int,
    model: FakeChatModel,
    registry: ToolRegistry | None = None,
    **kw: Any,
) -> RunResult:
    limits = kw.pop("limits", Limits(max_steps_item=6))
    with Session(engine) as session:
        return execute_run(
            run_id,
            session=session,
            sessions=sessionmaker(bind=engine),
            client=client_for(model),
            limits=limits,
            registry=registry,
            **kw,
        )


def count(engine: Engine, table: type) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(table)) or 0


def test_baseline_crash_restarts_from_zero(engine: Engine) -> None:
    run_id, _ = make(engine, 2)
    model = crashing(saved(1), at=2)  # item 1 saves, the process dies on item 2's first call
    try:
        go(engine, run_id, model)
    except Crash:
        pass
    else:
        raise AssertionError("the crash did not leave the loop")
    assert count(engine, Turn) == 0  # no checkpoints
    assert states(engine, run_id) == ("running", ["queued", "queued"])  # nothing written
    again = FakeChatModel(responses=[saved(1), saved(2)])
    result = go(engine, run_id, again)
    assert len(again.seen) == 2  # item 1 was extracted again
    assert [o.state for o in result.outcomes] == ["draft_saved", "draft_saved"]
    # queued in memory (MKC-23)
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval"] * 2)


def test_baseline_holds_approvals_in_memory_only(engine: Engine) -> None:
    run_id, _ = make(engine, 2)
    result = go(engine, run_id, FakeChatModel(responses=[saved(1), saved(2)]))
    assert count(engine, Draft) == 0
    assert result.memory is not None
    assert titles(result.memory.approvals) == ["draft 1", "draft 2"]
    assert [a["concept_key"] for a in result.memory.approvals] == ["MK-1", "MK-2"]
    with Session(engine) as session:
        assert RunMemory.load(session, run_id).approvals == []  # a new process has none


def test_baseline_saves_twice_without_a_key(engine: Engine) -> None:
    run_id, _ = make(engine, 1)
    twice = ai(tool_calls=[call("save_draft", "a", draft=valid_draft("v1")),
                           call("save_draft", "b", draft=valid_draft("v2"))])  # fmt: skip
    result = go(engine, run_id, FakeChatModel(responses=[twice]))
    assert result.memory is not None
    assert titles(result.memory.approvals) == ["v1", "v2"]


def test_full_saves_once_by_key(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="full")
    twice = ai(tool_calls=[call("save_draft", "a", draft=valid_draft("v1")),
                           call("save_draft", "b", draft=valid_draft("v2"))])  # fmt: skip
    result = go(engine, run_id, FakeChatModel(responses=[twice]))
    assert result.memory is None
    assert count(engine, Draft) == 1


def test_baseline_stops_at_the_run_step_limit(engine: Engine) -> None:
    run_id, _ = make(engine, 2)
    model = FakeChatModel(responses=[READ, READ, saved(1), saved(2)])
    go(engine, run_id, model, limits=Limits(max_steps_item=6, max_steps_run=2))
    assert len(model.seen) == 2
    assert count(engine, Turn) == 0
    with Session(engine) as session:
        run = session.get_one(Run, run_id)
        assert (run.state, run.stop_reason) == ("stopped", "run_step_limit")


def test_baseline_report_has_the_ended_items(engine: Engine) -> None:
    """A run stopped after item 1 ended writes item 1's end state; item 2 stays queued."""
    run_id, _ = make(engine, 2)
    model = FakeChatModel(responses=[saved(1), READ, READ])
    go(engine, run_id, model, limits=Limits(max_steps_item=6, max_steps_run=3))
    assert states(engine, run_id) == ("stopped", ["pending_approval", "queued"])


def test_baseline_sends_the_same_requests_as_full(engine: Engine) -> None:
    seen = {}
    for mode in ("full", "baseline"):
        with engine.begin() as conn:
            conn.execute(text("truncate run_log, turn, item, run restart identity cascade"))
        run_id, _ = make(engine, 2, mode=mode)
        model = FakeChatModel(responses=[READ, saved(1), READ, saved(2)])
        go(engine, run_id, model, registry=Tools().registry())
        seen[mode] = model.seen
        assert states(engine, run_id) == ("awaiting_approval", ["draft_saved", "draft_saved"])
    assert seen["full"] == seen["baseline"]


def _cached_registry(tools: Tools) -> ToolRegistry:
    return ToolRegistry(
        item=[
            Tool("extract_text", "Page text.", PageArgs, tools.extract_text, False, True,
                 cacheable=True),
            *[t for t in tools.registry().for_context("item") if t.name == "save_draft"],
        ],
        run=[],
    )  # fmt: skip


def test_baseline_skips_the_tool_cache(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("truncate tool_cache"))
    for mode, rows in (("baseline", 0), ("full", 1)):
        run_id, _ = make(engine, 1, mode=mode)
        model = FakeChatModel(responses=[READ, saved(1)])
        go(engine, run_id, model, registry=_cached_registry(Tools()), code_version="abc")
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from tool_cache")).scalar_one() == rows


def test_execute_run_builds_the_registry_with_the_tool_hooks(engine: Engine) -> None:
    """The executor no longer holds a registry: `execute_run` builds one per run and mode,
    and the tool hooks must reach it (MKC-19 traces every tool call)."""
    seen: list[ToolTrace] = []
    for mode in ("full", "baseline"):
        run_id, _ = make(engine, 1, mode=mode)
        go(engine, run_id, FakeChatModel(responses=[saved(1)]), tool_tracers=(seen.append,))
    pair = [("save_draft", True), ("enqueue_approval", True)]  # the harness queues (MKC-23)
    assert [(t.tool, t.ok) for t in seen] == pair + pair


class _AfterFirstItem(FaultInjector):
    """No fault: it only notes when an item has ended, so `should_stop` can say yes then."""

    def __init__(self) -> None:
        super().__init__(FaultPlan())
        self.ended = 0

    def item_ended(self, outcome: Any) -> None:
        self.ended += 1


def test_baseline_sigterm_writes_nothing(engine: Engine) -> None:
    """A shutdown after item 1 ended leaves nothing behind: the next claim starts over."""
    run_id, _ = make(engine, 2)
    hook = _AfterFirstItem()
    model = FakeChatModel(responses=[saved(1), saved(2)])
    result = go(engine, run_id, model, faults=hook, should_stop=lambda: hook.ended >= 1)
    assert [o.state for o in result.outcomes] == ["draft_saved"]
    assert states(engine, run_id) == ("running", ["queued", "queued"])
    assert count(engine, Turn) == 0


def test_baseline_takes_running_items_too(engine: Engine) -> None:
    """An item a full-mode attempt left `running` is served again from its task."""
    run_id, _ = make_run(engine, "running", "queued")
    with Session(engine) as session, session.begin():
        session.execute(update(Run).where(Run.id == run_id).values(mode="baseline"))
    result = go(engine, run_id, FakeChatModel(responses=[saved(1), saved(2)]))
    assert [o.state for o in result.outcomes] == ["draft_saved", "draft_saved"]
    assert states(engine, run_id) == ("awaiting_approval", ["pending_approval", "pending_approval"])


def test_execute_run_differs_by_mode_only_in_the_switches(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 1 at the seam: what `execute_run` hands `process_run` for a full and a
    baseline run differs only in `switches`, `memory` and the `save_draft` and
    `enqueue_approval` functions (the queue in memory, MKC-23)."""
    seen: dict[str, dict[str, Any]] = {}

    def capture(run_id: int, **kw: Any) -> list[Any]:
        seen[(kw["switches"].checkpoints and "full") or "baseline"] = kw
        return []

    monkeypatch.setattr("mkc.harness.runner.process_run", capture)
    client = client_for(FakeChatModel(responses=[]))
    no_wait = lambda s: False  # noqa: E731  (one object for both runs)
    with Session(engine) as session:
        for mode in ("full", "baseline"):
            run_id, _ = make(engine, 1, mode=mode)
            execute_run(run_id, session=session, sessions=sessionmaker(bind=engine),
                        client=client, limits=Limits(), sleep=no_wait)  # fmt: skip
    full, baseline = seen["full"], seen["baseline"]
    assert full.keys() == baseline.keys()
    differ = {k for k in full if k != "registry" and full[k] != baseline[k]}
    assert differ == {"switches", "memory"}
    tools = [r.for_context("item") for r in (full["registry"], baseline["registry"])]
    assert [t.to_spec() for t in tools[0]] == [t.to_spec() for t in tools[1]]
    changed = {a.name for a, b in zip(*tools, strict=True) if a != b}
    assert changed == {"save_draft"}
    runs = [r.for_context("run") for r in (full["registry"], baseline["registry"])]
    assert [t.to_spec() for t in runs[0]] == [t.to_spec() for t in runs[1]]
    assert {a.name for a, b in zip(*runs, strict=True) if a != b} == {"enqueue_approval"}
