"""MKC-13.3: ModelClient over a fake LangChain chat model (live mode, no network)."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from mkc.models.client import CallTrace, ModelClient
from mkc.models.config import ModelsConfig
from mkc.models.types import (
    ROLES,
    Image,
    Message,
    ModelError,
    Provider,
    ToolCall,
    ToolSpec,
)
from tests.models.fakes import FakeChatModel, ai, fake


def config() -> ModelsConfig:
    roles: dict[str, Any] = {role: {"provider": "openrouter", "model": "a/cheap"} for role in ROLES}
    roles["judge"] = {"provider": "anthropic", "model": "c-haiku"}
    return ModelsConfig.model_validate(
        {
            "eur_per_usd": 0.9,
            "timeout_seconds": 90,
            "roles": roles,
            "contract_models": {
                "openrouter": "a/cheap",
                "gemini": "g",
                "anthropic": "c-haiku",
                "meta": "m",
            },
            "prices": {
                "openrouter": {"a/cheap": {"input": 1.0, "output": 4.0}},
                "gemini": {"g": {"input": 0, "output": 0}},
                "anthropic": {"c-haiku": {"input": 2.0, "output": 10.0}},
                "meta": {"m": {"input": 0.1, "output": 0.3}},
            },
        }
    )


class Built:
    """A factory that hands out one fake model and records what it was asked for."""

    def __init__(self, model: FakeChatModel) -> None:
        self.model = model
        self.calls: list[tuple[Provider, str, float]] = []

    def __call__(self, provider: Provider, model: str, timeout: float) -> FakeChatModel:
        self.calls.append((provider, model, timeout))
        return self.model


def client(
    model: FakeChatModel, traces: list[CallTrace] | None = None
) -> tuple[ModelClient, Built]:
    factory = Built(model)
    tracers = [traces.append] if traces is not None else []
    return ModelClient(config(), factory, mode="live", tracers=tracers), factory


USER = [Message(role="system", content="Be brief."), Message(role="user", content="Hi")]


class LookupLbs(BaseModel):
    code: str = Field(description="13-digit LBS code")


LOOKUP = ToolSpec(name="lookup_lbs", description="Look up an LBS code.", args=LookupLbs)


class Verdict(BaseModel):
    code: str
    confident: bool


# --- chat -----------------------------------------------------------------------------


def test_chat_returns_text_usage_and_model_id() -> None:
    model = fake(ai("Hello", input_tokens=2000, output_tokens=500))
    reply = client(model)[0].chat("facts", USER)
    assert reply.text == "Hello"
    assert reply.tool_calls == []
    assert reply.model_id == "openrouter:a/cheap"
    assert reply.usage.input_tokens == 2000
    assert reply.usage.output_tokens == 500
    # (2000 x 1.0 + 500 x 4.0) / 1e6 USD x 0.9 = 0.0036 EUR
    assert reply.usage.cost_eur == pytest.approx(0.0036)
    assert reply.parsed is None


def test_role_picks_provider_model_and_timeout_from_config() -> None:
    model = fake(ai("ok"))
    the_client, factory = client(model)
    the_client.chat("judge", USER)
    assert factory.calls == [("anthropic", "c-haiku", 90)]


def test_cost_uses_the_role_s_own_price() -> None:
    model = fake(ai("ok", input_tokens=1_000_000, output_tokens=0))
    reply = client(model)[0].chat("judge", USER)
    assert reply.usage.cost_eur == pytest.approx(1.8)  # $2.00 x 0.9


def test_messages_are_converted_to_langchain() -> None:
    model = fake(ai("ok"))
    history = [
        *USER,
        Message(
            role="assistant",
            content="",
            tool_calls=(ToolCall(id="c1", name="lookup_lbs", args={"code": "1"}),),
        ),
        Message(role="tool", content="found", tool_call_id="c1"),
    ]
    client(model)[0].chat("facts", history)
    sent = model.seen[0]
    assert [type(m) for m in sent] == [SystemMessage, HumanMessage, AIMessage, ToolMessage]
    assert sent[1].content == "Hi"
    assert isinstance(sent[2], AIMessage)
    assert sent[2].tool_calls[0]["name"] == "lookup_lbs"
    assert sent[2].tool_calls[0]["args"] == {"code": "1"}
    assert isinstance(sent[3], ToolMessage)
    assert sent[3].tool_call_id == "c1"


def test_tool_message_without_call_id_is_refused() -> None:
    with pytest.raises(ValueError, match="tool_call_id"):
        client(fake(ai("ok")))[0].chat("facts", [Message(role="tool", content="x")])


def test_missing_usage_is_an_error_not_cost_zero() -> None:
    with pytest.raises(ModelError, match="usage"):
        client(fake(ai("ok", usage=False)))[0].chat("facts", USER)


# --- tools ----------------------------------------------------------------------------


def test_chat_with_tools_binds_pydantic_tools_and_maps_calls() -> None:
    model = fake(ai("", tool_calls=[{"id": "c1", "name": "lookup_lbs", "args": {"code": "9"}}]))
    reply = client(model)[0].chat_with_tools("facts", USER, [LOOKUP])
    assert reply.tool_calls == [ToolCall(id="c1", name="lookup_lbs", args={"code": "9"})]
    (bound,) = model.bound_tools
    assert bound["function"]["name"] == "lookup_lbs"
    assert bound["function"]["description"] == "Look up an LBS code."
    assert bound["function"]["parameters"]["properties"]["code"]["type"] == "string"
    assert bound["function"]["parameters"]["required"] == ["code"]


def test_chat_with_no_tools_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one tool"):
        client(fake(ai("ok")))[0].chat_with_tools("facts", USER, [])


# --- vision ---------------------------------------------------------------------------


def test_vision_adds_images_to_the_last_user_message() -> None:
    model = fake(ai("A table"))
    page = Image(media_type="image/png", data=b"\x89PNG fake")
    client(model)[0].vision("extract_vision", USER, [page])
    content = model.seen[0][1].content
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "Hi"}
    assert content[1]["type"] == "image"
    assert content[1]["mime_type"] == "image/png"
    assert content[1]["base64"] == "iVBORyBmYWtl"


def test_vision_without_images_or_user_message_is_refused() -> None:
    page = Image(media_type="image/png", data=b"x")
    with pytest.raises(ValueError, match="image"):
        client(fake(ai("ok")))[0].vision("extract_vision", USER, [])
    with pytest.raises(ValueError, match="user message"):
        client(fake(ai("ok")))[0].vision("extract_vision", USER[:1], [page])


# --- structured output ----------------------------------------------------------------


def test_chat_structured_returns_parsed_dict() -> None:
    call = {"id": "s1", "name": "Verdict", "args": {"code": "9", "confident": True}}
    model = fake(ai("", tool_calls=[call], input_tokens=10, output_tokens=5))
    reply = client(model)[0].chat_structured("facts", USER, Verdict)
    assert reply.parsed == {"code": "9", "confident": True}
    assert reply.usage.input_tokens == 10


def test_chat_structured_that_does_not_parse_is_an_error() -> None:
    call = {"id": "s1", "name": "Verdict", "args": {"code": "9"}}
    with pytest.raises(ModelError, match="structured output"):
        client(fake(ai("", tool_calls=[call])))[0].chat_structured("facts", USER, Verdict)


# --- latency and traces ---------------------------------------------------------------


def test_latency_is_measured() -> None:
    model = fake(ai("slow"))
    model.sleep = 0.05
    reply = client(model)[0].chat("facts", USER)
    assert reply.latency_ms >= 50


def test_each_call_is_traced_once() -> None:
    traces: list[CallTrace] = []
    the_client = client(fake(ai("a"), ai("b")), traces)[0]
    the_client.chat("facts", USER)
    the_client.chat_with_tools("explain", USER, [LOOKUP])
    assert [(t.role, t.method, t.mode, t.error) for t in traces] == [
        ("facts", "chat", "live", None),
        ("explain", "chat_with_tools", "live", None),
    ]
    assert traces[0].model_id == "openrouter:a/cheap"
    assert traces[0].usage is not None
    assert traces[0].usage.input_tokens == 100


def test_failed_call_is_traced_and_raised() -> None:
    traces: list[CallTrace] = []
    the_client = client(fake(error=TimeoutError("provider timed out")), traces)[0]
    with pytest.raises(TimeoutError):
        the_client.chat("facts", USER)
    (trace,) = traces
    assert trace.error == "TimeoutError: provider timed out"
    assert trace.usage is None


def test_a_failing_tracer_does_not_break_the_call() -> None:
    def broken(trace: CallTrace) -> None:
        raise RuntimeError("trace sink down")

    the_client = ModelClient(config(), Built(fake(ai("ok"))), mode="live", tracers=[broken])
    assert the_client.chat("facts", USER).text == "ok"
