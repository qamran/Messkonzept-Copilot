"""MKC-20.2: baseline is the same loop with the five switches off (design 8.5, decision 60).

No checkpoints, no tool cache, no durable queue (claims and end states stay in memory until
the run ends), and approvals in memory only.
"""

from typing import Any

from sqlalchemy import Engine, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Draft, Run, Turn
from mkc.harness.baseline import RunMemory
from mkc.harness.limits import Limits
from mkc.harness.runner import RunResult, execute_run
from mkc.harness.tools import Tool, ToolRegistry, ToolTrace
from tests.harness.conftest import make_run, states
from tests.harness.test_loop import PageArgs, Tools, call, client_for
from tests.harness.test_resume import Crash, crashing
from tests.models.fakes import FakeChatModel, ai

READ = ai(tool_calls=[call("extract_text", "r1", page=3)])


def saved(n: int) -> Any:
    return ai(tool_calls=[call("save_draft", f"s{n}", draft={"n": n})])


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
    assert states(engine, run_id) == ("awaiting_approval", ["draft_saved", "draft_saved"])


def test_baseline_holds_approvals_in_memory_only(engine: Engine) -> None:
    run_id, _ = make(engine, 2)
    result = go(engine, run_id, FakeChatModel(responses=[saved(1), saved(2)]))
    assert count(engine, Draft) == 0
    assert result.memory is not None
    assert [a["body"] for a in result.memory.approvals] == [{"n": 1}, {"n": 2}]
    assert [a["concept_key"] for a in result.memory.approvals] == ["MK-1", "MK-2"]
    with Session(engine) as session:
        assert RunMemory.load(session, run_id).approvals == []  # a new process has none


def test_baseline_saves_twice_without_a_key(engine: Engine) -> None:
    run_id, _ = make(engine, 1)
    twice = ai(tool_calls=[call("save_draft", "a", draft={"v": 1}),
                           call("save_draft", "b", draft={"v": 2})])  # fmt: skip
    result = go(engine, run_id, FakeChatModel(responses=[twice]))
    assert result.memory is not None
    assert [a["body"] for a in result.memory.approvals] == [{"v": 1}, {"v": 2}]


def test_full_saves_once_by_key(engine: Engine) -> None:
    run_id, _ = make(engine, 1, mode="full")
    twice = ai(tool_calls=[call("save_draft", "a", draft={"v": 1}),
                           call("save_draft", "b", draft={"v": 2})])  # fmt: skip
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
    assert states(engine, run_id) == ("stopped", ["draft_saved", "queued"])


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
    assert [(t.tool, t.ok) for t in seen] == [("save_draft", True), ("save_draft", True)]
