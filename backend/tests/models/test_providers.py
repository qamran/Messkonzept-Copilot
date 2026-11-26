"""MKC-13.5: the provider factory. OpenRouter requests carry zero-data-retention routing."""

import json
import time
from pathlib import Path
from typing import Any

import httpx
import openrouter
import pytest
from langchain_core.messages import HumanMessage

from mkc.config import Settings
from mkc.models.client import ModelClient
from mkc.models.providers import META_API_BASE, OPENROUTER_ROUTING, build_chat_model
from mkc.models.types import ModelConfigError, ReplayMiss
from tests.models.test_client import USER

KEYS = {
    "MKC_OPENROUTER_API_KEY": "or-test",
    "MKC_GOOGLE_API_KEY": "g-test",
    "MKC_ANTHROPIC_API_KEY": "a-test",
    "MKC_META_API_KEY": "m-test",
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    return Settings()


def test_openrouter_request_asks_for_zero_data_retention(settings: Settings) -> None:
    """The real ChatOpenRouter and SDK build the request; only the transport is fake."""
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(400, json={"error": {"code": 400, "message": "test stop"}})

    model = build_chat_model("openrouter", "a/cheap", settings, 120)
    model.client = openrouter.OpenRouter(  # type: ignore[attr-defined]
        api_key="or-test", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(Exception):  # noqa: B017 - the fake 400 ends the call
        model.invoke([HumanMessage(content="Hi")])
    (body,) = sent
    assert body["model"] == "a/cheap"
    assert body["provider"]["zdr"] is True
    assert body["provider"]["data_collection"] == "deny"


def test_openrouter_routing_constant() -> None:
    assert OPENROUTER_ROUTING == {"zdr": True, "data_collection": "deny"}


def test_openrouter_gets_key_timeout_in_ms_and_no_retries(settings: Settings) -> None:
    model: Any = build_chat_model("openrouter", "a/cheap", settings, 120)
    assert model.openrouter_api_key.get_secret_value() == "or-test"
    assert model.request_timeout == 120_000
    assert model.max_retries == 0


def test_anthropic_gets_key_timeout_and_no_retries(settings: Settings) -> None:
    model: Any = build_chat_model("anthropic", "c-haiku", settings, 90)
    assert model.model == "c-haiku"
    assert model.anthropic_api_key.get_secret_value() == "a-test"
    assert model.default_request_timeout == 90
    assert model.max_retries == 0


def test_gemini_gets_key_timeout_and_no_retries(settings: Settings) -> None:
    model: Any = build_chat_model("gemini", "g-flash", settings, 90)
    assert model.model.endswith("g-flash")
    assert model.google_api_key.get_secret_value() == "g-test"
    assert model.timeout == 90
    assert model.max_retries == 0


def test_meta_uses_meta_api_with_key_timeout_and_no_retries(settings: Settings) -> None:
    model: Any = build_chat_model("meta", "m-spark", settings, 90)
    assert model.model_name == "m-spark"
    assert model.openai_api_key.get_secret_value() == "m-test"
    assert model.openai_api_base == META_API_BASE
    assert model.request_timeout == 90
    assert model.max_retries == 0


@pytest.mark.parametrize(
    ("provider", "env"),
    [
        ("openrouter", "MKC_OPENROUTER_API_KEY"),
        ("gemini", "MKC_GOOGLE_API_KEY"),
        ("anthropic", "MKC_ANTHROPIC_API_KEY"),
        ("meta", "MKC_META_API_KEY"),
    ],
)
def test_missing_key_is_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, provider: Any, env: str
) -> None:
    for name in KEYS:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ModelConfigError, match=env):
        build_chat_model(provider, "x", Settings(), 60)


# --- ModelClient.from_settings ---------------------------------------------------------


def test_from_settings_replay_needs_no_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in KEYS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MKC_MODEL_MODE", "replay")
    monkeypatch.setenv("MKC_MODEL_REPLAY_DIR", str(tmp_path))
    client = ModelClient.from_settings(Settings())
    with pytest.raises(ReplayMiss):
        client.chat("facts", USER)


def test_from_settings_replay_without_dir_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_MODEL_MODE", "replay")
    monkeypatch.delenv("MKC_MODEL_REPLAY_DIR", raising=False)
    with pytest.raises(ModelConfigError, match="MKC_MODEL_REPLAY_DIR"):
        ModelClient.from_settings(Settings())


def test_from_settings_reads_models_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MKC_MODEL_MODE", "live")
    monkeypatch.setenv("MKC_MODELS_FILE", str(tmp_path / "missing.yaml"))
    with pytest.raises(ModelConfigError, match="not found"):
        ModelClient.from_settings(Settings())


# --- no hidden retries (decision 52; found after the 503 mock hung) --------------------


@pytest.mark.parametrize("status", [503, 500, 429])
def test_openrouter_sends_exactly_one_request_on_errors(settings: Settings, status: int) -> None:
    """The SDK's own default is exponential backoff on 5XX for up to an hour. The factory
    must switch it off, so a 503 fails at once and the harness decides (E4, decision 42)."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status, json={"error": {"code": status, "message": "down"}})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    model = build_chat_model("openrouter", "a/cheap", settings, 120, http_client=http)
    started = time.perf_counter()
    with pytest.raises(Exception):  # noqa: B017 - any error; the point is one request
        model.invoke([HumanMessage(content="Hi")])
    assert len(sent) == 1
    assert time.perf_counter() - started < 5
    body = json.loads(sent[0].content)
    assert body["provider"] == {"zdr": True, "data_collection": "deny"}
