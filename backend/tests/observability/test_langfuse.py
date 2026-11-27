"""MKC-19.3: `LangfuseSink` against the real SDK, exporting to memory (no network, no keys)."""

import json
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mkc.config import Settings
from mkc.observability.langfuse import LangfuseSink, make_client
from mkc.observability.trace import TraceRecord

EUR_PER_USD = 0.9145
TRACE = "0123456789abcdef0123456789abcdef"
MODEL = TraceRecord(kind="model", run_id=7, item_id=3, step=2, name="openrouter:a/cheap",
                    ok=True, mode="live", input_tokens=100, output_tokens=20,
                    cost_eur=Decimal("0.000300"), latency_ms=840,
                    detail={"role": "extract_vision", "method": "chat_with_tools"})  # fmt: skip
ATTR = "langfuse.observation."


@pytest.fixture
def exported() -> Iterator[tuple[LangfuseSink, InMemorySpanExporter]]:
    exporter = InMemorySpanExporter()
    client = Langfuse(public_key=f"pk-lf-test-{uuid.uuid4().hex}", secret_key="sk-lf-test",
                      base_url="http://127.0.0.1:9", span_exporter=exporter)  # fmt: skip
    yield LangfuseSink(client, eur_per_usd=EUR_PER_USD), exporter
    client.shutdown()


def spans(sink: LangfuseSink, exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    sink.flush()
    return list(exporter.get_finished_spans())


def attrs(span: ReadableSpan) -> dict[str, Any]:
    return dict(span.attributes or {})


def test_model_call_is_a_generation_in_the_run_s_trace(
    exported: tuple[LangfuseSink, InMemorySpanExporter],
) -> None:
    sink, exporter = exported
    sink.send(MODEL, TRACE)
    (span,) = spans(sink, exporter)
    found = attrs(span)
    assert format(span.context.trace_id, "032x") == TRACE
    assert found[ATTR + "type"] == "generation"
    assert found[ATTR + "model.name"] == "openrouter:a/cheap"
    assert json.loads(found[ATTR + "usage_details"]) == {"input": 100, "output": 20}
    usd = json.loads(found[ATTR + "cost_details"])["total"]
    assert usd == pytest.approx(0.0003 / EUR_PER_USD)  # Langfuse counts USD
    assert found[ATTR + "metadata.item_id"] == "3" and found[ATTR + "metadata.step"] == "2"
    assert json.loads(found[ATTR + "metadata.mode"]) == "live"  # metadata values are JSON
    duration_ms = ((span.end_time or 0) - (span.start_time or 0)) / 1_000_000
    assert 840 <= duration_ms < 850  # the call's latency, plus the time to build the span
    assert not any(key.startswith((ATTR + "input", ATTR + "output")) for key in found)


def test_replayed_call_sends_no_cost(exported: tuple[LangfuseSink, InMemorySpanExporter]) -> None:
    sink, exporter = exported
    sink.send(TraceRecord(**(MODEL.__dict__ | {"mode": "replay"})), TRACE)
    (span,) = spans(sink, exporter)
    assert ATTR + "cost_details" not in attrs(span)
    assert json.loads(attrs(span)[ATTR + "metadata.mode"]) == "replay"


def test_failed_call_has_level_error(exported: tuple[LangfuseSink, InMemorySpanExporter]) -> None:
    sink, exporter = exported
    failed = TraceRecord(**(MODEL.__dict__ | {"ok": False, "error": "TimeoutError: slow",
                                              "public_error": "TimeoutError",
                                              "input_tokens": None, "output_tokens": None,
                                              "cost_eur": None}))  # fmt: skip
    sink.send(failed, TRACE)
    found = attrs(spans(sink, exporter)[0])
    assert found[ATTR + "level"] == "ERROR"
    assert found[ATTR + "status_message"] == "TimeoutError"  # never the error text (MKC-20.5)
    assert ATTR + "usage_details" not in found and ATTR + "cost_details" not in found


def test_tool_call_and_stop(exported: tuple[LangfuseSink, InMemorySpanExporter]) -> None:
    sink, exporter = exported
    sink.send(TraceRecord(kind="tool", run_id=7, item_id=3, step=2, name="extract_text",
                          ok=True, latency_ms=12, detail={"ctx": "item", "refused": False,
                                                          "cached": True}), TRACE)  # fmt: skip
    sink.send(TraceRecord(kind="stop", run_id=7, item_id=3, name="step_limit", ok=False,
                          detail={"scope": "item", "steps": 12}), TRACE)  # fmt: skip
    tool, stop = spans(sink, exporter)
    assert (tool.name, attrs(tool)[ATTR + "type"]) == ("extract_text", "tool")
    assert attrs(tool)[ATTR + "metadata.cached"] == "true"
    assert (stop.name, attrs(stop)[ATTR + "type"]) == ("stop: step_limit", "event")
    assert attrs(stop)[ATTR + "level"] == "WARNING"
    assert {format(s.context.trace_id, "032x") for s in (tool, stop)} == {TRACE}


def test_from_settings_needs_both_keys() -> None:
    assert LangfuseSink.from_settings(Settings(langfuse_public_key="")) is None
    built = LangfuseSink.from_settings(
        Settings(
            langfuse_public_key=f"pk-lf-test-{uuid.uuid4().hex}",
            langfuse_secret_key="sk-lf-test",  # type: ignore[arg-type]
            langfuse_base_url="http://127.0.0.1:9",
        )
    )
    assert isinstance(built, LangfuseSink)
    built.shutdown()


def test_only_our_own_observations_leave(
    exported: tuple[LangfuseSink, InMemorySpanExporter],
) -> None:
    """The SDK becomes the global OpenTelemetry provider, and its default filter passes any
    span with `gen_ai.*` attributes, such as the Anthropic SDK's own tracing with the prompt.
    Only the sink's observations may leave (decision 59: no content)."""
    exporter = InMemorySpanExporter()
    settings = Settings(langfuse_public_key=f"pk-lf-test-{uuid.uuid4().hex}",
                        langfuse_secret_key="sk-lf-test",  # type: ignore[arg-type]
                        langfuse_base_url="http://127.0.0.1:9")  # fmt: skip
    client = make_client(settings, span_exporter=exporter)
    try:
        sink = LangfuseSink(client, eur_per_usd=EUR_PER_USD)
        with trace.get_tracer("anthropic").start_as_current_span("chat") as foreign:
            foreign.set_attribute("gen_ai.prompt", "the prompt text")
        sink.send(MODEL, TRACE)
        assert [s.name for s in spans(sink, exporter)] == ["extract_vision"]
    finally:
        client.shutdown()


class _Obs:
    def __init__(self, type_: str, input_: Any = None) -> None:
        self.type, self.input, self.output = type_, input_, None


class _Api:
    def __init__(self) -> None:
        self.asked: dict[str, Any] = {}
        self.observations = self

    def get_many(self, **kw: Any) -> Any:
        self.asked = kw
        return type("Page", (), {"data": [_Obs("GENERATION"), _Obs("TOOL", {"x": 1})]})()


class _Client:
    def __init__(self) -> None:
        self.api = _Api()

    def auth_check(self) -> bool:
        return True


def test_read_back_a_trace_s_observations() -> None:
    """For the real run: what Langfuse stored, by type, and whether any carries content."""
    client = _Client()
    sink = LangfuseSink(client, eur_per_usd=EUR_PER_USD)  # type: ignore[arg-type]
    assert sink.auth_check() is True
    assert sink.observations(TRACE) == [("GENERATION", False), ("TOOL", True)]
    assert client.api.asked["trace_id"] == TRACE
