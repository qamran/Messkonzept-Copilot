"""Tool registry core (MKC-14.1): allow-lists, validation and structured errors."""

from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from mkc.harness.tools import Tool, ToolEnv, ToolError, ToolRegistry, ToolResult, ToolTrace
from mkc.models.types import ToolCall, ToolSpec


class PageArgs(BaseModel):
    page: int = Field(ge=1)


class UrlArgs(BaseModel):
    operator_id: str


ENV = ToolEnv(run_id=7, item_id=42, document_hash="sha256:abc", concept_key="MK-3")
"""The harness's ids for the item; the model never supplies them (decision 54)."""


class Spy:
    """A tool function that records its calls and the environment it got."""

    def __init__(self, result: Any = "done") -> None:
        self.calls: list[BaseModel] = []
        self.envs: list[ToolEnv] = []
        self.result = result

    def __call__(self, args: BaseModel, env: ToolEnv) -> Any:
        self.calls.append(args)
        self.envs.append(env)
        return self.result


def make_registry(
    item_fn: Spy | None = None, run_fn: Spy | None = None, traces: list[ToolTrace] | None = None
) -> ToolRegistry:
    item = Tool(
        name="extract_text",
        description="Text of one page.",
        args_model=PageArgs,
        fn=item_fn or Spy(),
        side_effect=False,
        deterministic=True,
    )
    run = Tool(
        name="fetch_document",
        description="Fetch an operator's PDF.",
        args_model=UrlArgs,
        fn=run_fn or Spy(),
        side_effect=True,
        deterministic=False,
    )
    tracers = [traces.append] if traces is not None else []
    return ToolRegistry(item=[item], run=[run], tracers=tracers)


def call(name: str, **args: Any) -> ToolCall:
    return ToolCall(id="call-1", name=name, args=args)


def test_valid_call_runs_the_tool_with_validated_args() -> None:
    spy = Spy(result={"text": "Messkonzept 1"})
    result = make_registry(item_fn=spy).execute(call("extract_text", page="3"), "item", ENV)
    assert result == ToolResult(ok=True, data={"text": "Messkonzept 1"})
    assert spy.calls == [PageArgs(page=3)]


def test_tool_gets_the_harness_environment() -> None:
    spy = Spy()
    make_registry(item_fn=spy).execute(call("extract_text", page=1), "item", ENV)
    assert spy.envs == [ENV]


def test_run_operations_get_an_environment_without_item_ids() -> None:
    spy = Spy()
    env = ToolEnv(run_id=7)
    make_registry(run_fn=spy).execute(call("fetch_document", operator_id="x"), "run", env)
    assert spy.envs == [env]
    assert (env.item_id, env.document_hash, env.concept_key) == (None, None, None)


def test_tool_env_is_immutable() -> None:
    with pytest.raises(AttributeError):
        ENV.item_id = 1  # type: ignore[misc]


def test_unknown_tool_returns_structured_error() -> None:
    result = make_registry().execute(call("delete_catalogue", confirm=True), "item", ENV)
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "unknown_tool"
    assert "delete_catalogue" in result.error.message


def test_run_level_tool_requested_in_item_context_is_refused_and_not_executed() -> None:
    spy = Spy()
    registry = make_registry(run_fn=spy)
    # plausible arguments: they would validate, so only the context check can stop the call
    result = registry.execute(call("fetch_document", operator_id="stromnetz-berlin"), "item", ENV)
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "tool_not_allowed"
    assert spy.calls == []


def test_run_level_tool_runs_in_run_context() -> None:
    spy = Spy()
    result = make_registry(run_fn=spy).execute(call("fetch_document", operator_id="x"), "run", ENV)
    assert result.ok
    assert len(spy.calls) == 1


def test_invalid_args_return_validation_error() -> None:
    spy = Spy()
    result = make_registry(item_fn=spy).execute(call("extract_text", page=0), "item", ENV)
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "invalid_args"
    assert "page" in result.error.message
    assert spy.calls == []


def test_unexpected_args_are_invalid() -> None:
    result = make_registry().execute(call("extract_text", page=1, url="http://x"), "item", ENV)
    assert result.error is not None
    assert result.error.code == "invalid_args"


def test_tool_exception_becomes_structured_error() -> None:
    def boom(args: BaseModel, env: ToolEnv) -> Any:
        raise RuntimeError("pdf is broken")

    registry = make_registry(item_fn=boom)  # type: ignore[arg-type]
    result = registry.execute(call("extract_text", page=1), "item", ENV)
    assert result.error is not None
    assert result.error.code == "tool_failed"
    assert "pdf is broken" in result.error.message


def test_not_implemented_tool_returns_not_implemented() -> None:
    def todo(args: BaseModel, env: ToolEnv) -> Any:
        raise NotImplementedError("comes in MKC-22")

    registry = make_registry(item_fn=todo)  # type: ignore[arg-type]
    result = registry.execute(call("extract_text", page=1), "item", ENV)
    assert result.error is not None
    assert result.error.code == "not_implemented"


def test_refusals_are_counted_in_the_trace() -> None:
    traces: list[ToolTrace] = []
    registry = make_registry(traces=traces)
    registry.execute(call("nope"), "item", ENV)
    registry.execute(call("fetch_document", operator_id="x"), "item", ENV)
    registry.execute(call("extract_text", page=0), "item", ENV)
    registry.execute(call("extract_text", page=1), "item", ENV)
    assert [t.error_code for t in traces] == [
        "unknown_tool",
        "tool_not_allowed",
        "invalid_args",
        None,
    ]
    assert [t.refused for t in traces] == [True, True, False, False]
    assert sum(t.refused for t in traces) == 2
    assert all(t.ctx == "item" for t in traces)


def test_failing_tracer_does_not_break_the_call() -> None:
    def bad(trace: ToolTrace) -> None:
        raise RuntimeError("langfuse down")

    tool = Tool("extract_text", "Text.", PageArgs, Spy(), side_effect=False, deterministic=True)
    registry = ToolRegistry(item=[tool], run=[], tracers=[bad])
    assert registry.execute(call("extract_text", page=1), "item", ENV).ok


def test_side_effect_tool_cannot_be_registered_in_item_context() -> None:
    tool = Tool("commit_record", "Commit.", UrlArgs, Spy(), side_effect=True, deterministic=False)
    with pytest.raises(ValueError, match="side effect"):
        ToolRegistry(item=[tool], run=[])


def test_duplicate_names_are_refused() -> None:
    tool = Tool("extract_text", "Text.", PageArgs, Spy(), side_effect=False, deterministic=True)
    with pytest.raises(ValueError, match="extract_text"):
        ToolRegistry(item=[tool, tool], run=[])
    with pytest.raises(ValueError, match="extract_text"):
        ToolRegistry(item=[tool], run=[tool])


def test_registry_cannot_be_extended() -> None:
    registry = make_registry()
    tools = registry.for_context("item")
    assert isinstance(tools, tuple)
    assert [t.name for t in tools] == ["extract_text"]
    assert not any(hasattr(registry, m) for m in ("register", "add", "add_tool"))
    with pytest.raises(AttributeError):
        registry.item = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        registry._all["x"] = tools[0]  # type: ignore[index]


def test_tool_result_needs_exactly_one_of_data_and_error() -> None:
    error = ToolError(code="tool_failed", message="x")
    with pytest.raises(ValidationError):
        ToolResult(ok=True, error=error)
    with pytest.raises(ValidationError):
        ToolResult(ok=False)
    with pytest.raises(ValidationError):
        ToolResult(ok=False, data=1, error=error)
    assert ToolResult(ok=False, error=error).error == error
    assert ToolResult(ok=True, data=None).ok


def test_to_spec_matches_model_client_tool_spec() -> None:
    tool = make_registry().for_context("item")[0]
    spec = ToolSpec(name="extract_text", description="Text of one page.", args=PageArgs)
    assert tool.to_spec() == spec


@pytest.mark.parametrize(
    "env",
    [
        ToolEnv(run_id=7),
        ToolEnv(run_id=7, item_id=42, document_hash="h"),
        ToolEnv(run_id=7, item_id=42, concept_key="MK-3"),
    ],
)
def test_item_call_without_the_item_ids_is_a_harness_error(env: ToolEnv) -> None:
    spy = Spy()
    with pytest.raises(ValueError, match="item context needs"):
        make_registry(item_fn=spy).execute(call("extract_text", page=1), "item", env)
    assert spy.calls == []
