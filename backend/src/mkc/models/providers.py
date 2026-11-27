"""Provider factory (MKC-13.5): the only module that imports provider packages.

Every chat model gets its key from `Settings` (never the provider's own environment
variable), the configured timeout and no retries of its own: retries belong to the harness,
so faults such as a 429 stay visible to it (E4).
"""

import anthropic
import httpx
import openai
import openrouter
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_openrouter import ChatOpenRouter
from openrouter.utils import BackoffStrategy, RetryConfig
from pydantic import SecretStr

from mkc.config import Settings
from mkc.models.client import ChatModelFactory
from mkc.models.types import (
    ModelAuthError,
    ModelConfigError,
    ModelError,
    Provider,
    TransientModelError,
)

OPENROUTER_ROUTING = {"zdr": True, "data_collection": "deny"}
"""OpenRouter provider preferences: only zero-data-retention endpoints, no data collection."""

NO_RETRIES = RetryConfig("none", BackoffStrategy(500, 500, 1.0, 0), False)
"""The OpenRouter SDK retries 5XX with backoff for up to an hour when no retry config is given
(`openrouter/chat.py`), even with `max_retries=0` on the LangChain class. This switches it off."""

META_API_BASE = "https://api.meta.ai/v1"
"""Meta's OpenAI-compatible API (the Llama API at api.llama.com closed on 6 July 2026).
Confirmed by the live contract run of 26.11.2026 (tools, structured output and vision passed)."""

_KEY_SETTING: dict[Provider, tuple[str, str]] = {
    "openrouter": ("openrouter_api_key", "MKC_OPENROUTER_API_KEY"),
    "gemini": ("google_api_key", "MKC_GOOGLE_API_KEY"),
    "anthropic": ("anthropic_api_key", "MKC_ANTHROPIC_API_KEY"),
    "meta": ("meta_api_key", "MKC_META_API_KEY"),
}


def _key(provider: Provider, settings: Settings) -> SecretStr:
    field, env = _KEY_SETTING[provider]
    key: SecretStr = getattr(settings, field)
    if not key.get_secret_value():
        raise ModelConfigError(f"{env} is not set; provider {provider!r} needs it in live mode")
    return key


def build_chat_model(
    provider: Provider,
    model: str,
    settings: Settings,
    timeout: float,
    *,
    http_client: httpx.Client | None = None,
) -> BaseChatModel:
    """The LangChain chat model for one provider and model. `http_client` is a test seam for
    OpenRouter (a mock transport); production leaves it None."""
    key = _key(provider, settings)
    if provider == "openrouter":
        timeout_ms = round(timeout * 1000)  # milliseconds in this package
        chat = ChatOpenRouter(  # type: ignore[call-arg]  # pydantic alias `model`
            model=model,
            api_key=key,
            timeout=timeout_ms,
            max_retries=0,
            openrouter_provider=dict(OPENROUTER_ROUTING),
        )
        chat.client = openrouter.OpenRouter(
            api_key=key.get_secret_value(),
            timeout_ms=timeout_ms,
            retry_config=NO_RETRIES,
            client=http_client,
        )
        return chat
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model, google_api_key=key, request_timeout=timeout, retries=0
        )
    if provider == "anthropic":
        return ChatAnthropic(model=model, api_key=key, timeout=timeout, max_retries=0)
    return ChatOpenAI(
        model=model, api_key=key, base_url=META_API_BASE, timeout=timeout, max_retries=0
    )


def make_factory(settings: Settings) -> ChatModelFactory:
    def factory(provider: Provider, model: str, timeout: float) -> BaseChatModel:
        return build_chat_model(provider, model, settings, timeout)

    return factory


AUTH_STATUS = frozenset({401, 403})
"""The provider refused the key: a setup error that would fail every item (MKC-18)."""

_TRANSIENT_TYPES: tuple[type[BaseException], ...] = (
    httpx.TransportError,  # timeouts and network errors (the OpenRouter SDK lets them through)
    TimeoutError,
    openai.APIConnectionError,  # includes APITimeoutError (Meta's OpenAI-compatible API)
    anthropic.APIConnectionError,
)


def classify_error(error: Exception) -> ModelError | None:
    """Our error class for a provider error, or None to pass it on unchanged (MKC-18).

    By duck typing on `status_code` (OpenRouter, OpenAI, Anthropic) or `code` (Google), so a
    new SDK version with new class names still maps: 401/403 are `ModelAuthError`; 408, 429
    and 5xx, timeouts and network errors are `TransientModelError`. Everything else (a 400,
    a bug) stays as it is and fails the item.
    """
    if isinstance(error, ModelError):
        return None
    status = _status(error)
    name = type(error).__name__
    if status in AUTH_STATUS:
        return ModelAuthError(f"the provider refused the key: HTTP {status} ({name})")
    if status in (408, 429) or (status is not None and 500 <= status <= 599):
        return TransientModelError(f"HTTP {status} ({name})", _retry_after(error))
    if isinstance(error, _TRANSIENT_TYPES):
        return TransientModelError(f"{name}: {error}"[:300])
    return None


def _status(error: Exception) -> int | None:
    for attribute in ("status_code", "code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
            return value
    return None


def _retry_after(error: Exception) -> float | None:
    """`Retry-After` in seconds from the error's response; a date or junk gives None."""
    response = getattr(error, "raw_response", None) or getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    value = headers.get("retry-after") if headers is not None else None
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None
