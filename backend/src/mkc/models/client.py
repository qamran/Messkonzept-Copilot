"""`ModelClient`: the one way to call a model (MKC-13, AGENTS.md model rules).

LangChain chat models do the provider plumbing underneath (`bind_tools`,
`with_structured_output`); this wrapper picks the model per role from config, converts our
plain types, and records tokens, EUR cost, latency and a trace per call.
"""

import base64
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel

from mkc.config import Settings
from mkc.models.config import DEFAULT_MODELS_FILE, ModelsConfig, load_models_config
from mkc.models.replay import ReplayStore, replay_key
from mkc.models.types import (
    Image,
    Message,
    ModelConfigError,
    ModelError,
    ModelMode,
    ModelReply,
    Provider,
    Role,
    ToolCall,
    ToolSpec,
    Usage,
)

log = logging.getLogger(__name__)

Method = Literal["chat", "chat_with_tools", "vision", "chat_structured"]

ChatModelFactory = Callable[[Provider, str, float], BaseChatModel]
"""Builds the chat model for (provider, model, timeout in seconds)."""


@dataclass(frozen=True)
class TraceScope:
    """Where a model call belongs: the harness's run, item and step (MKC-19). The caller
    passes it with the call, so a trace that arrives late still lands in its place."""

    run_id: int
    item_id: int | None = None
    step: int | None = None


@dataclass(frozen=True)
class CallTrace:
    """One model call, as the trace hooks see it. `usage` is None when the call failed."""

    role: Role
    method: Method
    mode: ModelMode
    model_id: str
    latency_ms: int
    usage: Usage | None
    error: str | None
    scope: TraceScope | None = None


Tracer = Callable[[CallTrace], None]

Classifier = Callable[[Exception], ModelError | None]
"""Maps a provider error to `TransientModelError` or `ModelAuthError` (None: unchanged)."""


def _image_block(image: Image) -> dict[str, Any]:
    data = base64.b64encode(image.data).decode("ascii")
    return {"type": "image", "base64": data, "mime_type": image.media_type}


def to_langchain(message: Message) -> BaseMessage:
    """Our message → a LangChain message; images become standard base64 content blocks."""
    if message.role == "system":
        return SystemMessage(content=message.content)
    if message.role == "user":
        if not message.images:
            return HumanMessage(content=message.content)
        blocks: list[str | dict[Any, Any]] = [{"type": "text", "text": message.content}]
        blocks += [_image_block(i) for i in message.images]
        return HumanMessage(content=blocks)
    if message.role == "assistant":
        calls = [{"id": c.id, "name": c.name, "args": c.args} for c in message.tool_calls]
        return AIMessage(content=message.content, tool_calls=calls)
    if not message.tool_call_id:
        raise ValueError("a tool message needs the tool_call_id it answers")
    return ToolMessage(content=message.content, tool_call_id=message.tool_call_id)


def tool_schema(spec: ToolSpec) -> dict[str, Any]:
    """A tool in the OpenAI function format, which every LangChain provider accepts."""
    tool = convert_to_openai_tool(spec.args)
    tool["function"]["name"] = spec.name
    tool["function"]["description"] = spec.description
    return tool


class ModelClient:
    """`chat`, `chat_with_tools`, `vision` and `chat_structured` for a role.

    With `classify` (set by `from_settings`), a provider error leaves as `TransientModelError`
    or `ModelAuthError` when it is one, with the original as `__cause__` (MKC-18)."""

    def __init__(
        self,
        config: ModelsConfig,
        factory: ChatModelFactory,
        *,
        mode: ModelMode = "live",
        store: ReplayStore | None = None,
        tracers: Sequence[Tracer] = (),
        classify: Classifier | None = None,
    ) -> None:
        if mode != "live" and store is None:
            raise ModelConfigError(f"mode {mode!r} needs a replay store (MKC_MODEL_REPLAY_DIR)")
        self._config = config
        self._factory = factory
        self._mode: ModelMode = mode
        self._store = store
        self._tracers = list(tracers)
        self._classify = classify

    @classmethod
    def from_settings(cls, settings: Settings, tracers: Sequence[Tracer] = ()) -> "ModelClient":
        """The client as configured by `MKC_MODEL_MODE`, `MKC_MODELS_FILE` and
        `MKC_MODEL_REPLAY_DIR`. Keys are only checked when a live call builds a model."""
        from mkc.models.providers import classify_error, make_factory  # provider packages

        path = Path(settings.models_file) if settings.models_file else DEFAULT_MODELS_FILE
        config = load_models_config(path)
        store = None
        if settings.model_mode != "live":
            if not settings.model_replay_dir:
                raise ModelConfigError(f"mode {settings.model_mode!r} needs MKC_MODEL_REPLAY_DIR")
            store = ReplayStore(Path(settings.model_replay_dir))
        return cls(
            config,
            make_factory(settings),
            mode=settings.model_mode,
            store=store,
            tracers=tracers,
            classify=classify_error,
        )

    # --- public methods ---------------------------------------------------------------

    def chat(
        self, role: Role, messages: Sequence[Message], *, scope: TraceScope | None = None
    ) -> ModelReply:
        return self._call(role, "chat", messages, lambda model: model, scope=scope)

    def chat_with_tools(
        self,
        role: Role,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        *,
        scope: TraceScope | None = None,
    ) -> ModelReply:
        if not tools:
            raise ValueError("chat_with_tools needs at least one tool")
        schemas = [tool_schema(t) for t in tools]
        return self._call(
            role,
            "chat_with_tools",
            messages,
            lambda m: m.bind_tools(schemas),
            tools=tools,
            scope=scope,
        )

    def vision(
        self,
        role: Role,
        messages: Sequence[Message],
        images: Sequence[Image],
        *,
        scope: TraceScope | None = None,
    ) -> ModelReply:
        """Like `chat`, with the images added to the last user message."""
        if not images:
            raise ValueError("vision needs at least one image")
        users = [i for i, m in enumerate(messages) if m.role == "user"]
        if not users:
            raise ValueError("vision needs a user message to attach the images to")
        last = users[-1]
        with_images = list(messages)
        target = messages[last]
        with_images[last] = target.model_copy(update={"images": (*target.images, *images)})
        return self._call(role, "vision", with_images, lambda model: model, scope=scope)

    def chat_structured(
        self,
        role: Role,
        messages: Sequence[Message],
        schema: type[BaseModel],
        *,
        scope: TraceScope | None = None,
    ) -> ModelReply:
        """A reply whose `parsed` field is `schema`, validated, as a plain dict."""
        return self._call(
            role,
            "chat_structured",
            messages,
            lambda model: model.with_structured_output(schema, include_raw=True),
            schema=schema,
            scope=scope,
        )

    # --- one call ---------------------------------------------------------------------

    def _call(
        self,
        role: Role,
        method: Method,
        messages: Sequence[Message],
        prepare: Callable[[BaseChatModel], Any],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: type[BaseModel] | None = None,
        scope: TraceScope | None = None,
    ) -> ModelReply:
        target = self._config.roles[role]
        model_id = f"{target.provider}:{target.model}"
        lc_messages = [to_langchain(m) for m in messages]
        key = replay_key(
            role=role,
            model_id=model_id,
            method=method,
            messages=messages,
            tools=tools,
            schema=schema,
        )
        start = time.perf_counter()
        try:
            if self._mode == "replay" and self._store is not None:
                reply = self._store.get(key)  # never builds a provider client
                self._trace(
                    CallTrace(role, method, "replay", model_id, 0, reply.usage, None, scope)
                )
                return reply
            chat_model = self._factory(target.provider, target.model, self._config.timeout_seconds)
            output = prepare(chat_model).invoke(lc_messages)
            raw, parsed = _split(output, method)
            latency_ms = round((time.perf_counter() - start) * 1000)
            reply = self._reply(target.provider, target.model, raw, parsed, latency_ms)
            if self._mode == "record" and self._store is not None:
                self._store.put(key, reply)
        except Exception as error:
            latency_ms = round((time.perf_counter() - start) * 1000)
            self._trace(
                CallTrace(role, method, self._mode, model_id, latency_ms, None, _err(error), scope)
            )
            mapped = self._classify(error) if self._classify is not None else None
            if mapped is not None:
                raise mapped from error  # transient or auth (MKC-18); the cause is kept
            raise
        self._trace(
            CallTrace(role, method, self._mode, model_id, latency_ms, reply.usage, None, scope)
        )
        return reply

    def _reply(
        self,
        provider: Provider,
        model: str,
        raw: AIMessage,
        parsed: dict[str, Any] | None,
        latency_ms: int,
    ) -> ModelReply:
        usage = raw.usage_metadata
        if usage is None:
            raise ModelError(f"{provider}:{model} reported no token usage; cost unknown")
        cost = self._config.cost_eur(provider, model, usage["input_tokens"], usage["output_tokens"])
        return ModelReply(
            text=str(raw.text),
            tool_calls=[
                ToolCall(id=c.get("id") or "", name=c["name"], args=c["args"])
                for c in raw.tool_calls
            ],
            usage=Usage(
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cost_eur=cost,
            ),
            model_id=f"{provider}:{model}",
            latency_ms=latency_ms,
            parsed=parsed,
        )

    def _trace(self, trace: CallTrace) -> None:
        for tracer in self._tracers:
            try:
                tracer(trace)
            except Exception:
                log.exception("trace hook failed for %s %s", trace.role, trace.method)


def _split(output: Any, method: Method) -> tuple[AIMessage, dict[str, Any] | None]:
    """The raw AIMessage and, for structured output, the parsed result as a dict."""
    if method != "chat_structured":
        if not isinstance(output, AIMessage):
            raise ModelError(f"expected an AIMessage, got {type(output).__name__}")
        return output, None
    raw = output.get("raw")
    parsed = output.get("parsed")
    if not isinstance(raw, AIMessage):
        raise ModelError("structured output returned no raw message")
    if output.get("parsing_error") is not None or not isinstance(parsed, BaseModel):
        raise ModelError(f"structured output did not parse: {output.get('parsing_error')}")
    return raw, parsed.model_dump(mode="json")


def _err(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


# --- Embeddings (MKC-49) ------------------------------------------------------------------

EmbedCall = Callable[[Sequence[str]], tuple[list[list[float]], int]]
"""One provider request: texts → (vectors in input order, input tokens)."""

EmbedFactory = Callable[[Provider, str, int, float], EmbedCall]
"""Builds the embedding call for (provider, model, dimensions, timeout in seconds)."""

EMBED_BATCH_SIZE = 32
"""Texts per request; a law Absatz can reach about 2,000 tokens (decision 72), so a request
stays well inside the model's limits."""


@dataclass(frozen=True)
class EmbeddingReply:
    vectors: list[list[float]]
    model_id: str
    input_tokens: int
    cost_eur: float
    latency_ms: int


class EmbeddingClient:
    """Embeddings through the provider layer: the vector sibling of `ModelClient` (MKC-49).

    Same `models.yaml` price table and the same error classes (`classify`), and like
    `ModelClient` it never imports a provider package itself. Live only: replies are not
    recorded, so `record` and `replay` mode refuse to embed rather than spend or guess."""

    def __init__(
        self,
        config: ModelsConfig,
        factory: EmbedFactory,
        *,
        provider: Provider,
        model: str,
        dim: int,
        mode: ModelMode = "live",
        classify: Classifier | None = None,
        batch_size: int = EMBED_BATCH_SIZE,
    ) -> None:
        if mode != "live":
            raise ModelConfigError(
                f"embeddings run in live mode only (MKC_MODEL_MODE=live), not {mode!r}"
            )
        config.cost_eur(provider, model, 0, 0)  # no price: refused before any spend
        self._config = config
        self._factory = factory
        self._provider: Provider = provider
        self._model = model
        self._dim = dim
        self._classify = classify
        self._batch_size = batch_size

    @classmethod
    def from_settings(
        cls, settings: Settings, *, provider: Provider, model: str, dim: int
    ) -> "EmbeddingClient":
        from mkc.models.providers import classify_error, make_embed_factory  # provider packages

        path = Path(settings.models_file) if settings.models_file else DEFAULT_MODELS_FILE
        return cls(
            load_models_config(path),
            make_embed_factory(settings),
            provider=provider,
            model=model,
            dim=dim,
            mode=settings.model_mode,
            classify=classify_error,
        )

    def embed(self, texts: Sequence[str]) -> EmbeddingReply:
        """The texts' vectors in input order, sent in batches."""
        start = time.perf_counter()
        vectors: list[list[float]] = []
        tokens = 0
        if texts:
            call = self._factory(
                self._provider, self._model, self._dim, self._config.timeout_seconds
            )
            for at in range(0, len(texts), self._batch_size):
                try:
                    batch, used = call(texts[at : at + self._batch_size])
                except Exception as error:
                    mapped = self._classify(error) if self._classify is not None else None
                    if mapped is not None:
                        raise mapped from error
                    raise
                vectors += batch
                tokens += used
        return EmbeddingReply(
            vectors=vectors,
            model_id=f"{self._provider}:{self._model}",
            input_tokens=tokens,
            cost_eur=self._config.cost_eur(self._provider, self._model, tokens, 0),
            latency_ms=round((time.perf_counter() - start) * 1000),
        )
