"""MKC-18.3: `ModelClient` turns provider errors into our error classes (decision 58).

The OpenRouter cases send a real request through the real SDK to a mock transport, so the
test sees the exceptions production sees (not guessed class names).
"""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mkc.config import Settings
from mkc.models.client import ModelClient
from mkc.models.providers import build_chat_model, classify_error
from mkc.models.types import (
    ModelAuthError,
    ModelConfigError,
    ModelError,
    Provider,
    TransientModelError,
)
from tests.models.test_client import USER, config
from tests.models.test_providers import KEYS

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    return Settings()


def openrouter_client(settings: Settings, handler: Handler) -> ModelClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))

    def factory(provider: Provider, model: str, timeout: float) -> Any:
        return build_chat_model("openrouter", model, settings, timeout, http_client=http)

    return ModelClient(config(), factory, mode="live", classify=classify_error)


def status(code: int, **headers: str) -> Handler:
    body = {"error": {"code": code, "message": "x"}}
    return lambda request: httpx.Response(code, headers=headers, json=body)


def raises(error: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return handler


def call(client: ModelClient) -> None:
    client.chat("extract_vision", USER)


def test_429_with_retry_after_is_transient(settings: Settings) -> None:
    with pytest.raises(TransientModelError) as caught:
        call(openrouter_client(settings, status(429, **{"retry-after": "7"})))
    assert caught.value.retry_after == 7.0
    assert type(caught.value.__cause__).__name__ == "TooManyRequestsResponseError"


@pytest.mark.parametrize("code", [500, 502, 503])
def test_5xx_is_transient_without_retry_after(settings: Settings, code: int) -> None:
    with pytest.raises(TransientModelError) as caught:
        call(openrouter_client(settings, status(code)))
    assert caught.value.retry_after is None


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout("slow"), httpx.ConnectError("refused")],
    ids=["timeout", "network"],
)
def test_timeouts_and_network_errors_are_transient(settings: Settings, error: Exception) -> None:
    with pytest.raises(TransientModelError):
        call(openrouter_client(settings, raises(error)))


@pytest.mark.parametrize("code", [401, 403])
def test_auth_errors_are_setup_errors(settings: Settings, code: int) -> None:
    with pytest.raises(ModelAuthError) as caught:
        call(openrouter_client(settings, status(code)))
    assert isinstance(caught.value, ModelConfigError)  # a setup error: it stops the run


def test_a_bad_request_is_not_mapped(settings: Settings) -> None:
    with pytest.raises(Exception) as caught:
        call(openrouter_client(settings, status(400)))
    assert not isinstance(caught.value, ModelError)
    assert type(caught.value).__name__ == "BadRequestResponseError"


# --- classify_error on the shapes of the other SDKs ---------------------------------------


class _Response:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = httpx.Headers(headers)


class StatusError(Exception):
    """Shaped like `openai.APIStatusError` / `anthropic.APIStatusError`."""

    def __init__(self, status_code: int, headers: dict[str, str] | None = None) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code
        self.response = _Response(headers or {})


@pytest.mark.parametrize("code", [408, 429, 500, 529])
def test_classify_maps_transient_status_codes(code: int) -> None:
    assert isinstance(classify_error(StatusError(code)), TransientModelError)


def test_classify_reads_retry_after_from_the_response() -> None:
    mapped = classify_error(StatusError(429, {"retry-after": "2.5"}))
    assert isinstance(mapped, TransientModelError) and mapped.retry_after == 2.5


def test_classify_ignores_a_retry_after_date() -> None:
    mapped = classify_error(StatusError(503, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}))
    assert isinstance(mapped, TransientModelError) and mapped.retry_after is None


@pytest.mark.parametrize(
    "error", [ValueError("bug"), StatusError(400), StatusError(404), KeyError("x")]
)
def test_classify_leaves_other_errors_alone(error: Exception) -> None:
    assert classify_error(error) is None


def test_classify_maps_builtin_timeouts() -> None:
    assert isinstance(classify_error(TimeoutError("slow")), TransientModelError)


def test_without_a_classifier_errors_pass_unchanged(settings: Settings) -> None:
    http = httpx.Client(transport=httpx.MockTransport(status(429)))
    client = ModelClient(
        config(),
        lambda p, m, t: build_chat_model("openrouter", m, settings, t, http_client=http),
        mode="live",
    )
    with pytest.raises(Exception) as caught:
        call(client)
    assert type(caught.value).__name__ == "TooManyRequestsResponseError"
