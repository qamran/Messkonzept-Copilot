"""MKC-22 (MKC-14 review finding 2): nothing the model sends makes `ToolRegistry.execute` raise,
also when an argument model's validator raises something other than `ValueError`, or a
tool's exception cannot be turned into text. MKC-22 adds the first real argument models.

Pinned: a validator that raises `TypeError`, `AttributeError` or `KeyError` gives
`invalid_args` (with and without a tool cache); an exception whose `__str__` fails gives
`tool_failed`. Neither raises.
"""

from typing import Any

import pytest
from pydantic import BaseModel, field_validator

from mkc.harness.tools import Tool, ToolEnv, ToolRegistry
from mkc.models.types import ToolCall

ENV = ToolEnv(run_id=1, item_id=2, document_hash="abc", concept_key="1")


def _args_raising(error: type[Exception]) -> type[BaseModel]:
    class Args(BaseModel):
        page: Any

        @field_validator("page")
        @classmethod
        def _check(cls, value: Any) -> Any:
            raise error("the validator broke")

    return Args


class NoCache:
    """A `ResultCache` that never hits and stores nothing."""

    def get(self, tool: str, args: dict[str, Any], document_hash: str) -> Any:
        return None

    def put(self, tool: str, args: dict[str, Any], document_hash: str, data: Any) -> None:
        pass


@pytest.mark.parametrize("error", [TypeError, AttributeError, KeyError])
@pytest.mark.parametrize("cached", [False, True])
def test_a_validator_that_raises_gives_invalid_args(error: type[Exception], cached: bool) -> None:
    calls: list[Any] = []
    tool = Tool("t", "t", _args_raising(error), lambda a, e: calls.append(a), side_effect=False,
                deterministic=True, cacheable=True)  # fmt: skip
    registry = ToolRegistry(item=[tool], run=[])
    cache = NoCache() if cached else None
    result = registry.execute(ToolCall(id="c", name="t", args={"page": 1}), "item", ENV, cache)
    assert result.error is not None and result.error.code == "invalid_args"
    assert calls == []


class Unprintable(Exception):
    def __str__(self) -> str:
        raise RuntimeError("no text")


def test_an_exception_without_text_gives_tool_failed() -> None:
    class Args(BaseModel):
        page: int

    def broken(args: Any, env: ToolEnv) -> Any:
        raise Unprintable()

    tool = Tool("t", "t", Args, broken, side_effect=False, deterministic=True)
    result = ToolRegistry(item=[tool], run=[]).execute(
        ToolCall(id="c", name="t", args={"page": 1}), "item", ENV
    )
    assert result.error is not None and result.error.code == "tool_failed"
    assert "Unprintable" in result.error.message
