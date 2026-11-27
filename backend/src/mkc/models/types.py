"""Plain types for model calls (MKC-13). Callers never see LangChain objects."""

from dataclasses import dataclass
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["extract_vision", "facts", "explain", "judge", "gold_draft"]
"""What a model call is for; each role maps to a provider and model in `models.yaml`."""
ROLES: tuple[Role, ...] = get_args(Role)

Provider = Literal["openrouter", "gemini", "anthropic", "meta"]
"""`meta` is Meta's OpenAI-compatible API (api.meta.ai); the Llama API closed on 6 July 2026."""
PROVIDERS: tuple[Provider, ...] = get_args(Provider)

ModelMode = Literal["live", "record", "replay"]
"""`live` calls the provider; `record` calls it and stores the reply; `replay` only reads
stored replies and never builds a provider client."""


class ModelError(Exception):
    """Base class for provider-layer errors."""


class ModelConfigError(ModelError):
    """`models.yaml`, a setting or a key is missing or wrong."""


class ReplayMiss(ModelError):
    """Replay mode found no stored reply for the request."""


class ModelAuthError(ModelConfigError):
    """The provider refused the key (401) or the account has no credits (402): a setup error,
    it stops the run (MKC-18)."""


class TransientModelError(ModelError):
    """A 408, 429 or 5xx, a timeout or a network error: worth a retry (MKC-18).

    `retry_after` is the provider's `Retry-After` in seconds, when it sent one."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Image(_Frozen):
    """An image sent to a vision model."""

    media_type: str
    data: bytes


class ToolCall(_Frozen):
    """A tool call the model asked for. Arguments are not validated here."""

    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class Message(_Frozen):
    """One chat message. `tool` messages answer the tool call named by `tool_call_id`."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    images: tuple[Image, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call: its arguments are a Pydantic model."""

    name: str
    description: str
    args: type[BaseModel]


class Usage(_Frozen):
    input_tokens: int
    output_tokens: int
    cost_eur: float


class ModelReply(_Frozen):
    """What every `ModelClient` method returns. `parsed` is set by `chat_structured`."""

    text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage
    model_id: str
    latency_ms: int
    parsed: dict[str, Any] | None = None
