"""Tool registry with per-context allow-lists (MKC-14, design 8.1).

The model only sees the item context's tools. Run-level operations live in the same
registry so they get the same validation and tracing, but `execute` refuses them in the
item context without calling them. Every failure is a structured `ToolError` that goes
back to the model; nothing raises out of `execute`.

`side_effect` (decision 53): the tool reaches outside its own item (network, catalogue,
approval queue, or state a re-run with the same arguments cannot overwrite by key). Such a
tool can never be registered in the item context.

`ToolEnv` (decision 54): the harness's ids for the call. Tools key their work by these, never
by model arguments.
"""

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from mkc.models.types import ToolCall, ToolSpec

log = logging.getLogger(__name__)

Context = Literal["item", "run"]
CONTEXTS: tuple[Context, ...] = get_args(Context)

ErrorCode = Literal[
    "unknown_tool", "tool_not_allowed", "invalid_args", "not_implemented", "tool_failed"
]
REFUSALS: frozenset[ErrorCode] = frozenset({"unknown_tool", "tool_not_allowed"})
"""Error codes that count as refusals in the trace: the call was never allowed."""

_MAX_MESSAGE = 1000


@dataclass(frozen=True)
class ToolEnv:
    """The harness's ids for the call (decision 54). The model never sets these.

    Item tools get all four. Run-level operations get `run_id` and whatever else exists at
    that point (`fetch_document` runs before there is a document or an item).
    """

    run_id: int
    item_id: int | None = None
    document_hash: str | None = None
    concept_key: str | None = None
    step: int | None = None  # the item's model call this tool call answers (MKC-19)


@dataclass(frozen=True)
class Tool:
    """A tool: its arguments are validated against `args_model` before `fn` is called."""

    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[Any, ToolEnv], Any]
    side_effect: bool
    deterministic: bool
    cacheable: bool = False

    def to_spec(self) -> ToolSpec:
        """What `ModelClient.chat_with_tools` takes."""
        return ToolSpec(name=self.name, description=self.description, args=self.args_model)


class ToolError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ErrorCode
    message: str


class ToolResult(BaseModel):
    """`ok=True` carries `data` (may be None); `ok=False` carries `error` and no data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    data: Any = None
    error: ToolError | None = None

    @model_validator(mode="after")
    def _one_of_data_and_error(self) -> "ToolResult":
        if self.ok and self.error is not None:
            raise ValueError("an ok result has no error")
        if not self.ok and (self.error is None or self.data is not None):
            raise ValueError("a failed result has an error and no data")
        return self


@dataclass(frozen=True)
class ToolTrace:
    """One tool call, as the trace hooks see it. MKC-19's tracer can consume this."""

    tool: str
    ctx: Context
    ok: bool
    error_code: ErrorCode | None
    refused: bool
    latency_ms: int
    cached: bool = False
    run_id: int | None = None  # from `ToolEnv` (MKC-19)
    item_id: int | None = None
    step: int | None = None


ToolTracer = Callable[[ToolTrace], None]


class ResultCache(Protocol):
    """What `execute` needs from a cache (`mkc.harness.cache.ToolCache`)."""

    def get(self, tool: str, args: dict[str, Any], document_hash: str) -> Any: ...

    def put(self, tool: str, args: dict[str, Any], document_hash: str, data: Any) -> None: ...


class ToolRegistry:
    """Built once with the tools of each context; no tool can be added later."""

    __slots__ = ("_all", "_contexts", "_tracers")
    _all: Mapping[str, Tool]
    _contexts: Mapping[Context, tuple[Tool, ...]]
    _tracers: tuple[ToolTracer, ...]

    def __init__(
        self, *, item: Sequence[Tool], run: Sequence[Tool], tracers: Sequence[ToolTracer] = ()
    ) -> None:
        contexts: dict[Context, tuple[Tool, ...]] = {"item": tuple(item), "run": tuple(run)}
        everything: dict[str, Tool] = {}
        for ctx, tools in contexts.items():
            for tool in tools:
                if tool.name in everything:
                    raise ValueError(f"tool {tool.name!r} is registered twice")
                if tool.cacheable and not tool.deterministic:
                    raise ValueError(f"tool {tool.name!r} is cacheable but not deterministic")
                if ctx == "item" and tool.side_effect:
                    raise ValueError(
                        f"tool {tool.name!r} has a side effect and can't be an item tool"
                    )
                everything[tool.name] = tool
        object.__setattr__(self, "_contexts", MappingProxyType(contexts))
        object.__setattr__(self, "_all", MappingProxyType(everything))
        object.__setattr__(self, "_tracers", tuple(tracers))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("a ToolRegistry can't be changed after it is built")

    def for_context(self, ctx: Context) -> tuple[Tool, ...]:
        return self._contexts[ctx]

    def execute(
        self, call: ToolCall, ctx: Context, env: ToolEnv, cache: "ResultCache | None" = None
    ) -> ToolResult:
        """Run `call` in `ctx` with the harness's `env`, or return the error that says why not.

        Nothing the model sends makes this raise. An item-context call whose `env` lacks the
        item's ids is a harness bug and raises `ValueError` before any tool runs.
        """
        if ctx == "item" and None in (env.item_id, env.document_hash, env.concept_key):
            raise ValueError(
                f"the item context needs item_id, document_hash and concept_key: {env}"
            )
        start = time.perf_counter()
        result, cached = self._cached_run(call, ctx, env, cache)
        code = result.error.code if result.error else None
        latency_ms = round((time.perf_counter() - start) * 1000)
        trace = ToolTrace(
            call.name, ctx, result.ok, code, code in REFUSALS, latency_ms, cached,
            run_id=env.run_id, item_id=env.item_id, step=env.step,
        )  # fmt: skip
        self._trace(trace)
        return result

    def _cached_run(
        self, call: ToolCall, ctx: Context, env: ToolEnv, cache: "ResultCache | None"
    ) -> tuple[ToolResult, bool]:
        """The result and whether it came from `cache`.

        Only an allowed `cacheable` tool with valid arguments and a document is looked up, by
        its validated arguments; an `ok` result with a JSON form is stored. A cache database
        error propagates, like every database error in the loop.
        """
        tool = self._all.get(call.name)
        if (
            cache is None
            or tool is None
            or not tool.cacheable
            or tool not in self._contexts[ctx]
            or env.document_hash is None
        ):
            return self._run(call, ctx, env), False
        args = _valid_args(tool, call)
        if args is None:
            return self._run(call, ctx, env), False
        key = args.model_dump(mode="json")
        hit = cache.get(tool.name, key, env.document_hash)
        if hit is not None:
            return ToolResult(ok=True, data=hit.data), True
        result = self._run(call, ctx, env)
        if result.ok:
            try:
                data = result.model_dump(mode="json")["data"]
            except Exception:
                return result, False  # not JSON: the loop reports it; nothing is cached
            cache.put(tool.name, key, env.document_hash, data)
        return result, False

    def _run(self, call: ToolCall, ctx: Context, env: ToolEnv) -> ToolResult:
        tool = self._all.get(call.name)
        if tool is None:
            return _fail("unknown_tool", f"no tool named {call.name!r}")
        if tool not in self._contexts[ctx]:
            return _fail("tool_not_allowed", f"tool {call.name!r} is not allowed here")
        extra = sorted(set(call.args) - _accepted_names(tool.args_model))
        if extra:
            return _fail("invalid_args", f"unexpected arguments: {', '.join(extra)}")
        try:
            args = tool.args_model.model_validate(call.args)
        except ValidationError as error:
            return _fail("invalid_args", _validation_message(error))
        try:
            return ToolResult(ok=True, data=tool.fn(args, env))
        except NotImplementedError as error:
            return _fail("not_implemented", f"tool {call.name!r} is not built yet: {error}")
        except Exception as error:
            return _fail("tool_failed", f"{type(error).__name__}: {error}")

    def _trace(self, trace: ToolTrace) -> None:
        for tracer in self._tracers:
            try:
                tracer(trace)
            except Exception:
                log.exception("tool trace hook failed for %s", trace.tool)


def _fail(code: ErrorCode, message: str) -> ToolResult:
    return ToolResult(ok=False, error=ToolError(code=code, message=message[:_MAX_MESSAGE]))


def _valid_args(tool: Tool, call: ToolCall) -> BaseModel | None:
    if set(call.args) - _accepted_names(tool.args_model):
        return None
    try:
        return tool.args_model.model_validate(call.args)
    except ValidationError:
        return None


def _accepted_names(model: type[BaseModel]) -> set[str]:
    """Field names and aliases: the model sees nothing else, whatever its `extra` setting."""
    names = set(model.model_fields)
    names |= {f.alias for f in model.model_fields.values() if f.alias}
    return names


def _validation_message(error: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(p) for p in e['loc']) or '(args)'}: {e['msg']}" for e in error.errors()
    ]
    return "; ".join(parts)
