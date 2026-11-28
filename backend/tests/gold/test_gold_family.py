"""MKC-24.2, coordinator ruling 4 (decision 88): `gold_draft` must not share the model family
of `extract_vision`. The family is the vendor prefix before `/` (`google/...`); a direct
provider's model id without a slash counts as that provider's vendor."""

from typing import Any

import pytest

from mkc.models.config import ModelsConfig
from mkc.models.types import ROLES, ModelConfigError


def config(gold: tuple[str, str], extract: tuple[str, str]) -> ModelsConfig:
    roles: dict[str, Any] = {r: {"provider": extract[0], "model": extract[1]} for r in ROLES}
    roles["gold_draft"] = {"provider": gold[0], "model": gold[1]}
    prices: dict[str, dict[str, Any]] = {p: {"c": {"input": 0, "output": 0}} for p in
                                         ("openrouter", "gemini", "anthropic", "meta")}  # fmt: skip
    for provider, model in (gold, extract):
        prices[provider][model] = {"input": 1.0, "output": 1.0}
    return ModelsConfig.model_validate(
        {
            "eur_per_usd": 1.0,
            "timeout_seconds": 90,
            "roles": roles,
            "contract_models": {p: "c" for p in ("openrouter", "gemini", "anthropic", "meta")},
            "prices": prices,
        }
    )


@pytest.mark.parametrize(
    ("gold", "extract"),
    [
        (("openrouter", "google/gemini-3.5-flash-lite"), ("openrouter", "google/gemini-3.8-flash")),
        (("gemini", "gemini-3.5-flash-lite"), ("openrouter", "google/gemini-3.8-flash")),
        (("openrouter", "anthropic/claude-haiku-5.5"), ("anthropic", "claude-haiku-5-5")),
        (("openrouter", "meta-llama/llama-4-maverick"), ("meta", "muse-spark-1.3")),
        (("openrouter", "Google/gemini-x"), ("openrouter", "google/gemini-y")),
    ],
    ids=["same-vendor-on-openrouter", "gemini-direct", "anthropic-direct", "meta", "case"],
)
def test_the_same_model_family_is_refused(gold: tuple[str, str], extract: tuple[str, str]) -> None:
    from mkc.gold.draft import ensure_independent

    with pytest.raises(ModelConfigError, match="family"):
        ensure_independent(config(gold, extract))


@pytest.mark.parametrize(
    ("gold", "extract"),
    [
        (("openrouter", "anthropic/claude-haiku-5.5"), ("openrouter", "google/gemini-3.8-flash")),
        (("anthropic", "claude-haiku-5-5"), ("gemini", "gemini-3.5-flash-lite")),
    ],
)
def test_another_family_passes(gold: tuple[str, str], extract: tuple[str, str]) -> None:
    from mkc.gold.draft import ensure_independent

    ensure_independent(config(gold, extract))


def test_model_family_is_the_vendor_prefix() -> None:
    from mkc.gold.draft import model_family

    assert model_family("openrouter", "google/gemini-3.8-flash") == "google"
    assert model_family("openrouter", "meta-llama/llama-4-maverick") == "meta"
    assert model_family("gemini", "gemini-3.5-flash-lite") == "google"
    assert model_family("anthropic", "claude-haiku-5-5") == "anthropic"
