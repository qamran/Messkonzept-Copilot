"""MKC-13.6: live contract tests, one per provider (tool call + structured output round-trip).

They spend real money (a few cents in total) and need the provider keys, so they are
deselected by default. Run them on purpose:

    cd backend && uv run --env-file .env pytest -m live tests/models/test_contract_live.py -v

Each test skips when its key is not set. The result and the spend go into the status doc.
"""

from typing import Any

import pytest
from pydantic import BaseModel, Field

from mkc.config import Settings
from mkc.models.client import CallTrace, ModelClient
from mkc.models.config import load_models_config
from mkc.models.providers import make_factory
from mkc.models.types import PROVIDERS, ROLES, Image, Message, Provider, ToolSpec

pytestmark = pytest.mark.live

KEY_FIELD = {
    "openrouter": "openrouter_api_key",
    "gemini": "google_api_key",
    "anthropic": "anthropic_api_key",
    "meta": "meta_api_key",
}
CODE = "9992000000018"  # an LBS code from the public BDEW Codeliste (a fact, no PDF text)


class LookupLbs(BaseModel):
    code: str = Field(description="The 13-digit LBS code to look up")


class LbsAnswer(BaseModel):
    code: str = Field(description="The 13-digit LBS code from the question")
    digits: int = Field(description="How many digits the code has")


def contract_client(provider: Provider, traces: list[CallTrace]) -> ModelClient:
    settings = Settings()
    if not getattr(settings, KEY_FIELD[provider]).get_secret_value():
        pytest.skip(f"no API key for {provider}")
    config = load_models_config()
    model = config.contract_models[provider]
    roles: dict[str, Any] = {role: {"provider": provider, "model": model} for role in ROLES}
    config = config.model_validate({**config.model_dump(), "roles": roles})
    return ModelClient(config, make_factory(settings), mode="live", tracers=[traces.append])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_tool_call_round_trip(provider: Provider) -> None:
    traces: list[CallTrace] = []
    client = contract_client(provider, traces)
    tool = ToolSpec(name="lookup_lbs", description="Look up an LBS code.", args=LookupLbs)
    messages = [
        Message(role="system", content="Use the lookup_lbs tool. Do not answer in text."),
        Message(role="user", content=f"Look up the LBS code {CODE}."),
    ]
    reply = client.chat_with_tools("facts", messages, [tool])
    assert [c.name for c in reply.tool_calls] == ["lookup_lbs"]
    assert reply.tool_calls[0].args == {"code": CODE}
    assert reply.usage.input_tokens > 0
    assert reply.usage.cost_eur >= 0
    print(f"\n{provider} tools: {reply.model_id} {reply.usage} {reply.latency_ms} ms")

    # Answer the call and get a final text reply: the full round-trip.
    follow_up = [
        *messages,
        Message(role="assistant", content=reply.text, tool_calls=tuple(reply.tool_calls)),
        Message(
            role="tool",
            content="Strom: one MeLo, one MaLo (Einspeisung none).",
            tool_call_id=reply.tool_calls[0].id,
        ),
        Message(role="user", content="Now answer in one short sentence."),
    ]
    final = client.chat_with_tools("facts", follow_up, [tool])
    assert final.text.strip() or final.tool_calls
    assert [t.error for t in traces] == [None, None]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_structured_output_round_trip(provider: Provider) -> None:
    traces: list[CallTrace] = []
    client = contract_client(provider, traces)
    messages = [Message(role="user", content=f"The LBS code is {CODE}. Fill in the fields.")]
    reply = client.chat_structured("facts", messages, LbsAnswer)
    assert reply.parsed == {"code": CODE, "digits": 13}
    assert reply.usage.output_tokens > 0
    print(f"\n{provider} structured: {reply.model_id} {reply.usage} {reply.latency_ms} ms")


def red_png(size: int = 64) -> bytes:
    """A solid red PNG built with the standard library (no image in the repo). 64 px: Meta
    answered "white" for a 16 px image (26.11.2026), the same red at 64 px it got right."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\xff\x00\x00" * size for _ in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_vision_round_trip(provider: Provider) -> None:
    """Not a ticket criterion: proves the image block shape on each real provider."""
    traces: list[CallTrace] = []
    client = contract_client(provider, traces)
    messages = [Message(role="user", content="What colour is this image? Answer in one word.")]
    image = Image(media_type="image/png", data=red_png())
    reply = client.vision("extract_vision", messages, [image])
    assert "red" in reply.text.lower()
    print(f"\n{provider} vision: {reply.model_id} {reply.usage} {reply.latency_ms} ms")
