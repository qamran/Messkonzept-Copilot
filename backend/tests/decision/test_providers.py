"""MKC-46: the decision model is built in the provider factory (`providers.py`, the only module
that may import provider packages), with the OpenRouter key from `Settings`.

Construction only: no request is sent. The base URL is the development agent's choice (the
spike decides it); these tests pin only that the call goes to OpenRouter with our key.
"""

import pytest
from langchain_core.decisions import BaseDecisionModel
from pydantic import SecretStr

from mkc.config import Settings
from mkc.models.types import ModelConfigError


def _build(settings: Settings) -> BaseDecisionModel:
    from mkc.models.providers import build_decision_model

    return build_decision_model(settings)


def test_the_decision_model_is_a_langchain_decision_model() -> None:
    model = _build(Settings(openrouter_api_key=SecretStr("or-key")))
    assert isinstance(model, BaseDecisionModel)


def test_the_decision_model_is_the_configured_one() -> None:
    settings = Settings(openrouter_api_key=SecretStr("or-key"), decision_model="~typesafe/jev-x")
    assert _build(settings).model == "~typesafe/jev-x"


def test_the_key_comes_from_settings_never_from_typesafe_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe-env-key")
    model = _build(Settings(openrouter_api_key=SecretStr("or-key")))
    key = model.api_key  # type: ignore[attr-defined]
    assert (key.get_secret_value() if isinstance(key, SecretStr) else key) == "or-key"


def test_requests_go_to_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
    model = _build(Settings(openrouter_api_key=SecretStr("or-key")))
    assert "openrouter.ai" in model.base_url  # type: ignore[attr-defined]


def test_a_missing_openrouter_key_is_a_config_error() -> None:
    with pytest.raises(ModelConfigError, match="MKC_OPENROUTER_API_KEY"):
        _build(Settings(openrouter_api_key=SecretStr("")))
