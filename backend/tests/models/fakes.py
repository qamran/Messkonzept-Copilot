"""A fake LangChain chat model for the provider-layer tests (no network, no key)."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable


def ai(
    text: str = "",
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    input_tokens: int = 100,
    output_tokens: int = 20,
    usage: bool = True,
) -> AIMessage:
    """An AIMessage as a provider would return it, with token usage."""
    return AIMessage(
        content=text,
        tool_calls=[{**call, "type": "tool_call"} for call in tool_calls or []],
        usage_metadata=(
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }
            if usage
            else None
        ),
    )


class FakeChatModel(FakeMessagesListChatModel):
    """Replays the given AIMessages in order and records what it was sent and bound."""

    seen: list[list[BaseMessage]] = []
    bound_tools: list[Any] = []
    bind_kwargs: list[dict[str, Any]] = []
    error: Exception | None = None

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        self.seen.append(list(messages))
        if self.error is not None:
            raise self.error
        return super()._generate(messages, *args, **kwargs)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any]],
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        self.bound_tools.extend(tools)
        self.bind_kwargs.append(kwargs)
        return self  # type: ignore[return-value]


def fake(*responses: AIMessage, error: Exception | None = None) -> FakeChatModel:
    return FakeChatModel(
        responses=list(responses) or [ai("unused")],
        seen=[],
        bound_tools=[],
        bind_kwargs=[],
        error=error,
    )
