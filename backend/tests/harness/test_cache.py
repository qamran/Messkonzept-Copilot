"""MKC-16.4: deterministic document tools are cached (design 8.3, decision 56).

Cache rows outlive the per-test truncation, so every test uses its own `code_version`.
"""

import dataclasses
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Run
from mkc.harness.cache import ToolCache
from mkc.harness.loop import process_run
from mkc.harness.registry import default_registry
from mkc.harness.tools import Tool, ToolEnv, ToolRegistry, ToolTrace
from mkc.models.types import ToolCall
from tests.harness.conftest import make_run
from tests.harness.test_loop import SAVE, PageArgs, Tools, call, client_for, start
from tests.harness.test_resume import Crash, go
from tests.models.fakes import ai, fake

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
ENV = ToolEnv(run_id=1, item_id=1, document_hash="sha256:doc", concept_key="MK-1")


def version() -> str:
    return f"test-{uuid.uuid4().hex}"


class CountingTools(Tools):
    """`extract_text` is cacheable; it counts calls per page and can die or fail on demand."""

    def __init__(self, crash_on: int | None = None, fail_first: bool = False) -> None:
        super().__init__()
        self.pages: list[int] = []
        self.crash_on, self.fail_first = crash_on, fail_first
        self.traces: list[ToolTrace] = []

    def extract_text(self, args: PageArgs, env: ToolEnv) -> Any:
        self.pages.append(args.page)
        if len(self.pages) == self.crash_on:
            raise Crash
        if self.fail_first and len(self.pages) == 1:
            raise ValueError("pdf not readable yet")
        return f"text of page {args.page}"

    def registry(self) -> ToolRegistry:
        base = super().registry()
        item = [dataclasses.replace(t, cacheable=t.name == "extract_text")
                for t in base.for_context("item")]  # fmt: skip
        return ToolRegistry(item=item, run=base.for_context("run"), tracers=[self.traces.append])


def read(page: int, call_id: str = "") -> dict[str, Any]:
    return call("extract_text", call_id or f"r{page}", page=page)


def test_deterministic_tool_hits_cache_on_resume(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    code = version()
    first = fake(ai(tool_calls=[read(1)]), ai(tool_calls=[read(2), read(3)]))
    with pytest.raises(Crash):  # turn 2 dies in its second call, after page 2 was read
        go(engine, item_id, first, CountingTools(crash_on=3), code_version=code)

    tools = CountingTools()
    second = fake(ai(tool_calls=[read(2), SAVE]))
    go(engine, item_id, second, tools, code_version=code)
    assert tools.pages == []  # page 2 came from the cache
    assert [t.cached for t in tools.traces if t.tool == "extract_text"] == [True]


def execute(engine: Engine, tools: CountingTools, code: str, env: ToolEnv = ENV) -> Any:
    result = tools.registry().execute(
        ToolCall(id="c1", name="extract_text", args={"page": 4}), "item", env,
        ToolCache(sessionmaker(engine), code),
    )  # fmt: skip
    return result.model_dump(mode="json")


def test_a_cache_hit_gives_the_same_result_without_running_the_tool(engine: Engine) -> None:
    tools, code = CountingTools(), version()
    first = execute(engine, tools, code)
    assert execute(engine, tools, code) == first == {"ok": True, "data": "text of page 4",
                                                     "error": None}  # fmt: skip
    assert tools.pages == [4]
    assert [t.cached for t in tools.traces] == [False, True]


def test_another_document_or_code_version_misses(engine: Engine) -> None:
    tools, code = CountingTools(), version()
    execute(engine, tools, code)
    execute(engine, tools, code, dataclasses.replace(ENV, document_hash="sha256:other"))
    execute(engine, tools, version())
    assert tools.pages == [4, 4, 4]


def test_an_error_result_is_not_cached(engine: Engine) -> None:
    tools, code = CountingTools(fail_first=True), version()
    assert execute(engine, tools, code)["ok"] is False
    assert execute(engine, tools, code)["ok"] is True
    assert execute(engine, tools, code)["ok"] is True
    assert tools.pages == [4, 4]


def test_a_tool_that_is_not_cacheable_always_runs(engine: Engine) -> None:
    tools, code = Tools(), version()  # its extract_text is not cacheable
    cache = ToolCache(sessionmaker(engine), code)
    for _ in range(2):
        save = ToolCall(id="c", name="save_draft", args={"draft": {}})
        tools.registry().execute(save, "item", ENV, cache)
    assert len(tools.saved) == 2


def test_without_a_code_version_the_loop_does_not_cache(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    tools = CountingTools()
    go(engine, item_id, fake(ai(tool_calls=[read(5, "a")]), ai(tool_calls=[read(5, "b")]),
                             ai(tool_calls=[SAVE])), tools)  # fmt: skip
    assert tools.pages == [5, 5]


def test_cacheable_needs_deterministic() -> None:
    tool = Tool("t", "t", PageArgs, lambda a, e: None, side_effect=False, deterministic=False,
                cacheable=True)  # fmt: skip
    with pytest.raises(ValueError, match="cacheable"):
        ToolRegistry(item=[tool], run=[])


def test_the_default_registry_caches_the_three_document_tools() -> None:
    registry = default_registry()
    tools = registry.for_context("item") + registry.for_context("run")
    assert {t.name for t in tools if t.cacheable} == {
        "extract_text",
        "extract_tables",
        "render_region",
    }


def test_0006_creates_tool_cache_and_downgrades(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))

    def describe() -> tuple[set[str], set[tuple[str, ...]]]:
        engine = create_engine(database_env)
        try:
            with engine.connect() as conn:
                insp = inspect(conn)
                if not insp.has_table("tool_cache"):
                    return set(), set()
                columns = {c["name"] for c in insp.get_columns("tool_cache")}
                unique = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("tool_cache")
                }
                return columns, unique
        finally:
            engine.dispose()

    command.upgrade(config, "head")
    columns, unique = describe()
    assert columns == {"id", "tool", "code_version", "args_hash", "document_hash", "data",
                       "created_at"}  # fmt: skip
    assert unique == {("tool", "code_version", "args_hash", "document_hash")}
    command.downgrade(config, "0005")
    assert describe() == (set(), set())
    command.upgrade(config, "head")
    assert describe()[0] == columns


def test_a_cache_write_never_commits_the_callers_pending_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(Run(state="running"))  # pending in the caller's session
        ToolCache(sessionmaker(engine), version()).put("extract_text", {"page": 1}, "sha256:d", 1)
        session.rollback()
    with Session(engine) as session:
        assert session.query(Run).count() == 0


def test_process_run_passes_the_code_version_and_the_inline_limit(engine: Engine) -> None:
    run_id, ids = make_run(engine, "queued", "queued")  # two items of one document
    tools = CountingTools()
    model = fake(ai(tool_calls=[read(1)]), ai(tool_calls=[SAVE]),
                 ai(tool_calls=[read(1)]), ai(tool_calls=[SAVE]))  # fmt: skip
    with Session(engine) as session:
        process_run(run_id, session=session, client=client_for(model),
                    registry=tools.registry(), max_steps=5, code_version=version(),
                    inline_max_bytes=10)  # fmt: skip
    assert tools.pages == [1]  # the second item's read of page 1 hit the cache
    with Session(engine) as session:
        from mkc.db.models import Turn

        first = session.query(Turn).filter_by(item_id=ids[0], number=1).one()
        assert "result_ref" in first.tool_results[0]
