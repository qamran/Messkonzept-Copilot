"""`LangfuseSink`: trace records to Langfuse (MKC-19, decision 59).

- One trace per run: every observation carries the run's `trace_id` as its trace context.
- Model calls are generations (model, usage, cost in USD), tool calls are tool
  observations, retrievals (MKC-50) are retriever observations, stops and outages are
  events. A failed record has level `ERROR`.
- Metadata only: no prompts, replies, tool arguments or PDF text (decision 59).
- Cost: Langfuse counts USD, so the EUR cost goes back to USD with the rate of
  `models.yaml`; replayed calls send no cost (finding 13#4).
- Latency: the hook fires after the call, and the SDK starts a span when it is created, so
  the span ends `latency_ms` after it starts: the duration is right, the start is late by it.
- The SDK exports in a background thread; `flush` waits at most the export timeout.
"""

import time
from pathlib import Path
from typing import Any, Literal

from langfuse import Langfuse
from langfuse.span_filter import is_langfuse_span
from langfuse.types import TraceContext

from mkc.config import Settings
from mkc.models.config import DEFAULT_MODELS_FILE, load_models_config
from mkc.observability.trace import TraceRecord


def make_client(settings: Settings, **extra: Any) -> Langfuse:
    """The Langfuse client for the settings; `extra` goes to the constructor (tests pass an
    in-memory `span_exporter`).

    The SDK becomes the global OpenTelemetry provider, and its default filter also exports
    other libraries' `gen_ai.*` spans (the Anthropic SDK traces its calls with the prompt).
    `is_langfuse_span` lets only the sink's own observations leave (decision 59)."""
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
        timeout=settings.langfuse_timeout_seconds,
        environment=settings.langfuse_environment,
        release=settings.commit,
        should_export_span=is_langfuse_span,
        **extra,
    )


class LangfuseSink:
    def __init__(self, client: Langfuse, *, eur_per_usd: float) -> None:
        self._client = client
        self._eur_per_usd = eur_per_usd

    @classmethod
    def from_settings(cls, settings: Settings) -> "LangfuseSink | None":
        """The sink for the configured project; None when either key is not set."""
        secret = settings.langfuse_secret_key.get_secret_value()
        if not settings.langfuse_public_key or not secret:
            return None
        path = Path(settings.models_file) if settings.models_file else DEFAULT_MODELS_FILE
        return cls(make_client(settings), eur_per_usd=load_models_config(path).eur_per_usd)

    def send(self, record: TraceRecord, trace_id: str | None) -> None:
        context: TraceContext | None = None if trace_id is None else {"trace_id": trace_id}
        metadata = _metadata(record)
        if record.kind in ("stop", "outage"):
            self._client.create_event(
                trace_context=context,
                name=f"{record.kind}: {record.name}",
                metadata=metadata,
                level="WARNING" if record.kind == "stop" else "ERROR",
                status_message=record.public_error,
            )
            return
        level: Literal["ERROR"] | None = None if record.ok else "ERROR"
        if record.kind == "model":
            observation: Any = self._client.start_observation(
                trace_context=context,
                name=str(record.detail.get("role", "model")),
                as_type="generation",
                model=record.name,
                usage_details=_usage(record),
                cost_details=self._cost(record),
                metadata=metadata,
                level=level,
                status_message=record.public_error,
            )
        elif record.kind == "retrieval":
            observation = self._client.start_observation(
                trace_context=context,
                name=record.name,
                as_type="retriever",
                metadata=metadata,
                level=level,
                status_message=record.public_error,
            )
        else:
            observation = self._client.start_observation(
                trace_context=context,
                name=record.name,
                as_type="tool",
                metadata=metadata,
                level=level,
                status_message=record.public_error,
            )
        # the span started just now (the SDK takes no start time): end it `latency_ms` later
        observation.end(end_time=time.time_ns() + (record.latency_ms or 0) * 1_000_000)

    def auth_check(self) -> bool:
        """Whether Langfuse accepts the keys (one request)."""
        return bool(self._client.auth_check())

    def observations(self, trace_id: str) -> list[tuple[str, bool]]:
        """The trace's observations as Langfuse stored them: (type, has input or output)."""
        page = self._client.api.observations.get_many(trace_id=trace_id, limit=100)
        return [(o.type, o.input is not None or o.output is not None) for o in page.data]

    def flush(self) -> None:
        self._client.flush()

    def shutdown(self) -> None:
        self._client.shutdown()

    def _cost(self, record: TraceRecord) -> dict[str, float] | None:
        """USD, as Langfuse counts it; none for replays (finding 13#4) or failed calls."""
        if record.cost_eur is None or record.mode == "replay":
            return None
        return {"total": float(record.cost_eur) / self._eur_per_usd}


def _usage(record: TraceRecord) -> dict[str, int] | None:
    if record.input_tokens is None or record.output_tokens is None:
        return None
    return {"input": record.input_tokens, "output": record.output_tokens}


def _metadata(record: TraceRecord) -> dict[str, Any]:
    """Ids, mode, latency and the record's detail; never message or document content."""
    found: dict[str, Any] = {"run_id": record.run_id, "item_id": record.item_id,
                             "step": record.step, "mode": record.mode,
                             "latency_ms": record.latency_ms}  # fmt: skip
    if record.cost_eur is not None:
        found["cost_eur"] = str(record.cost_eur)
    found |= record.detail
    return {key: value for key, value in found.items() if value is not None}
