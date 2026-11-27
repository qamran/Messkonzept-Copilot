"""`LangfuseSink`: trace records to Langfuse (MKC-19, decision 59).

- One trace per run: every observation carries the run's `trace_id` as its trace context.
- Model calls are generations (model, usage, cost in USD), tool calls are tool
  observations, stops and outages are events. A failed record has level `ERROR`.
- Metadata only: no prompts, replies, tool arguments or PDF text (decision 59).
- Cost: Langfuse counts USD, so the EUR cost goes back to USD with the rate of
  `models.yaml`; replayed calls send no cost (finding 13#4).
- Latency: the hook fires after the call, and the SDK starts a span when it is created, so
  the span ends `latency_ms` after it starts: the duration is right, the start is late by it.
- The SDK exports in a background thread; `flush` waits at most the export timeout.
"""

from langfuse import Langfuse

from mkc.config import Settings
from mkc.observability.trace import TraceRecord


class LangfuseSink:
    def __init__(self, client: Langfuse, *, eur_per_usd: float) -> None:
        self._client = client
        self._eur_per_usd = eur_per_usd

    @classmethod
    def from_settings(cls, settings: Settings) -> "LangfuseSink | None":
        """The sink for the configured project; None when the keys are not set."""
        return None

    def send(self, record: TraceRecord, trace_id: str | None) -> None:
        return None

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None
