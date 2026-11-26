"""Tool registry with per-context allow-lists (MKC-14). Skeleton: behaviour comes next."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from mkc.models.types import ToolCall, ToolSpec

Context = Literal["item", "run"]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[Any], Any]
    side_effect: bool
    deterministic: bool

    def to_spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, args=self.args_model)


class ToolError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    data: Any = None
    error: ToolError | None = None


@dataclass(frozen=True)
class ToolTrace:
    tool: str
    ctx: Context
    ok: bool
    error_code: str | None
    refused: bool
    latency_ms: int


ToolTracer = Callable[[ToolTrace], None]


class ToolRegistry:
    def __init__(
        self, *, item: Sequence[Tool], run: Sequence[Tool], tracers: Sequence[ToolTracer] = ()
    ) -> None:
        self._tools = {"item": tuple(item), "run": tuple(run)}

    def for_context(self, ctx: Context) -> tuple[Tool, ...]:
        return self._tools[ctx]

    def execute(self, call: ToolCall, ctx: Context) -> ToolResult:
        return ToolResult(ok=True)
