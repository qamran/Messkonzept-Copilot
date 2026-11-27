"""Failure injection (MKC-20.3, feature 25, design section 12 E4, decision 60).

A `FaultPlan` says where faults happen; a `FaultInjector` makes them happen through three hooks
the loop calls, so every fault takes the real path:

- `timeout_at=n`: the n-th tool call times out. It returns `ok: false` with code `timeout`
  without running, and counts as a tool failure (the E4 "tool timeout").
- `rate_limit_at=n`: the n-th model call attempt raises `TransientModelError` (a 429) before
  it reaches the client, so `call_model` backs off and retries.
- `malformed_at=n`: the n-th model call attempt returns a reply with no tool call, at no cost,
  without reaching the client, so the re-prompt runs.
- `kill_at_turn=n`: the n-th model call attempt reaches the client, then `InjectedKill` is
  raised before its results are stored: the turn in flight is lost, and billed.
- `kill_during_approval=n`: `InjectedKill` right after the n-th item ends `draft_saved`
  (approvals come in MKC-23; until then a saved draft is the pending approval).

Counts are 1-based and count within one injector, so a fault fires at most once per
injector, which is once per process. A plan is never read from a setting: the CLI or a test
passes it explicitly, so a production worker can't inject faults.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from mkc.harness.states import ItemState
from mkc.harness.tools import ToolError, ToolResult
from mkc.models.types import ModelReply, ToolCall, TransientModelError, Usage


class FaultPlan(BaseModel):
    """Where faults happen; every field is a 1-based count, or None for no such fault."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timeout_at: int | None = Field(default=None, ge=1)
    rate_limit_at: int | None = Field(default=None, ge=1)
    malformed_at: int | None = Field(default=None, ge=1)
    kill_at_turn: int | None = Field(default=None, ge=1)
    kill_during_approval: int | None = Field(default=None, ge=1)


class InjectedKill(BaseException):
    """The process dies here. A `BaseException`, so the loop's `except Exception` never
    catches it and the retry thread passes it on."""


_PLANS = TypeAdapter(dict[str, FaultPlan])


def load_fault_plans(path: Path) -> dict[str, FaultPlan]:
    """A YAML mapping of plan name to plan; unknown keys and counts below 1 are refused."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _PLANS.validate_python(data)


class _Ended(Protocol):
    state: ItemState


class FaultInjector:
    """Fires the faults of one plan, each at most once. `fired` lists them in order."""

    def __init__(self, plan: FaultPlan) -> None:
        self.plan = plan
        self.fired: list[str] = []
        self._model_calls = 0
        self._tool_calls = 0
        self._drafts = 0

    def _fire(self, name: str, at: int | None, count: int) -> bool:
        if at != count or name in self.fired:
            return False
        self.fired.append(name)
        return True

    def model(self, fn: Callable[[], ModelReply]) -> Callable[[], ModelReply]:
        """Wrap one model call attempt (the callable `call_model` runs, once per attempt)."""

        def attempt() -> ModelReply:
            self._model_calls += 1
            n, plan = self._model_calls, self.plan
            if self._fire("rate_limit_at", plan.rate_limit_at, n):
                raise TransientModelError("injected 429 (fault plan)")
            if self._fire("malformed_at", plan.malformed_at, n):
                usage = Usage(input_tokens=0, output_tokens=0, cost_eur=0.0)
                return ModelReply(text="(injected malformed reply)", usage=usage,
                                  model_id="fault-plan", latency_ms=0)  # fmt: skip
            reply = fn()
            if self._fire("kill_at_turn", plan.kill_at_turn, n):
                raise InjectedKill(f"killed at model call {n} (fault plan)")
            return reply

        return attempt

    def tool(self, call: ToolCall) -> ToolResult | None:
        """A timeout result in place of the tool call, or None to run it."""
        self._tool_calls += 1
        if not self._fire("timeout_at", self.plan.timeout_at, self._tool_calls):
            return None
        error = ToolError(code="timeout", message=f"tool {call.name!r} timed out (fault plan)")
        return ToolResult(ok=False, error=error)

    def item_ended(self, outcome: _Ended | Any) -> None:
        """After an item's end state is stored (full) or kept in memory (baseline)."""
        if outcome.state is not ItemState.DRAFT_SAVED:
            return
        self._drafts += 1
        if self._fire("kill_during_approval", self.plan.kill_during_approval, self._drafts):
            raise InjectedKill(f"killed while draft {self._drafts} awaits approval (fault plan)")
