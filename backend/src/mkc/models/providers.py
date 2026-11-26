"""Provider factory (MKC-13.5): the only module that imports provider packages.

Every chat model gets its key from `Settings` (never the provider's own environment
variable), the configured timeout and no retries of its own: retries belong to the harness,
so faults such as a 429 stay visible to it (E4).
"""

import httpx
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
from mkc.models.types import ModelConfigError, Provider

OPENROUTER_ROUTING = {"zdr": True, "data_collection": "deny"}
"""OpenRouter provider preferences: only zero-data-retention endpoints, no data collection."""

NO_RETRIES = RetryConfig("none", BackoffStrategy(500, 500, 1.0, 0), False)
"""The OpenRouter SDK retries 5XX with backoff for up to an hour when no retry config is given
(`openrouter/chat.py`), even with `max_retries=0` on the LangChain class. This switches it off."""

META_API_BASE = "https://api.meta.ai/v1"
"""Meta's OpenAI-compatible API (the Llama API at api.llama.com closed on 6 July 2026).
Unverified: not yet confirmed by Meta's docs or a live call (MKC-13.6 does that)."""

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
