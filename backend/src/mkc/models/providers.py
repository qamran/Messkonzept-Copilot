"""Provider factory (MKC-13.5): the only module that imports provider packages.

Every chat model gets its key from `Settings` (never the provider's own environment
variable), the configured timeout and no retries of its own: retries belong to the harness,
so faults such as a 429 stay visible to it (E4).
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr

from mkc.config import Settings
from mkc.models.client import ChatModelFactory
from mkc.models.types import ModelConfigError, Provider

OPENROUTER_ROUTING = {"zdr": True, "data_collection": "deny"}
"""OpenRouter provider preferences: only zero-data-retention endpoints, no data collection."""

META_API_BASE = "https://api.meta.ai/v1"
"""Meta's OpenAI-compatible API (the Llama API at api.llama.com closed on 6 July 2026)."""

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
    provider: Provider, model: str, settings: Settings, timeout: float
) -> BaseChatModel:
    """The LangChain chat model for one provider and model."""
    key = _key(provider, settings)
    if provider == "openrouter":
        return ChatOpenRouter(  # type: ignore[call-arg]  # pydantic alias `model`
            model=model,
            api_key=key,
            timeout=round(timeout * 1000),  # milliseconds in this package
            max_retries=0,
            openrouter_provider=dict(OPENROUTER_ROUTING),
        )
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
