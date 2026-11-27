"""Failure injection (MKC-20.3, feature 25, decision 60)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mkc.harness.tools import ToolResult
from mkc.models.types import ModelReply, ToolCall


class FaultPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timeout_at: int | None = Field(default=None, ge=1)
    rate_limit_at: int | None = Field(default=None, ge=1)
    malformed_at: int | None = Field(default=None, ge=1)
    kill_at_turn: int | None = Field(default=None, ge=1)
    kill_during_approval: int | None = Field(default=None, ge=1)


class InjectedKill(BaseException):  # noqa: N818
    """The process dies here."""


def load_fault_plans(path: Path) -> dict[str, FaultPlan]:
    return {}


class FaultInjector:
    def __init__(self, plan: FaultPlan) -> None:
        self.plan = plan
        self.fired: list[str] = []

    def model(self, fn: Callable[[], ModelReply]) -> Callable[[], ModelReply]:
        return fn

    def tool(self, call: ToolCall) -> ToolResult | None:
        return None

    def item_ended(self, outcome: Any) -> None:
        return None
