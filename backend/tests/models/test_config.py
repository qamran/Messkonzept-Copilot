"""MKC-13.2: the role → provider/model mapping and the price table live in config, not code."""

from pathlib import Path
from typing import Any, get_args

import pytest
import yaml

from mkc.config import Settings
from mkc.models.config import DEFAULT_MODELS_FILE, ModelsConfig, load_models_config
from mkc.models.types import PROVIDERS, ROLES, ModelConfigError, Role


def _valid() -> dict[str, Any]:
    return {
        "eur_per_usd": 0.9,
        "timeout_seconds": 120,
        "roles": {role: {"provider": "openrouter", "model": "a/cheap"} for role in ROLES},
        "contract_models": {
            "openrouter": "a/cheap",
            "gemini": "g-flash",
            "anthropic": "c-haiku",
            "meta": "m-spark",
        },
        "prices": {
            "openrouter": {"a/cheap": {"input": 1.0, "output": 4.0}},
            "gemini": {"g-flash": {"input": 0, "output": 0}},
            "anthropic": {"c-haiku": {"input": 0.1, "output": 0.5}},
            "meta": {"m-spark": {"input": 1.25, "output": 4.25}},
        },
    }


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_roles_match_the_ticket() -> None:
    assert set(get_args(Role)) == {"extract_vision", "facts", "explain", "judge", "gold_draft"}
    assert set(ROLES) == set(get_args(Role))
    assert set(PROVIDERS) == {"openrouter", "gemini", "anthropic", "meta"}


def test_valid_file_loads(tmp_path: Path) -> None:
    config = load_models_config(_write(tmp_path, _valid()))
    assert config.roles["facts"].provider == "openrouter"
    assert config.roles["facts"].model == "a/cheap"
    assert config.timeout_seconds == 120


def test_cost_in_eur_from_usd_prices(tmp_path: Path) -> None:
    config = load_models_config(_write(tmp_path, _valid()))
    # 2000 in x $1/M + 500 out x $4/M = $0.004; x 0.9 = EUR 0.0036
    assert config.cost_eur("openrouter", "a/cheap", 2000, 500) == pytest.approx(0.0036)


def test_cost_of_unknown_model_raises(tmp_path: Path) -> None:
    config = load_models_config(_write(tmp_path, _valid()))
    with pytest.raises(ModelConfigError, match="no price"):
        config.cost_eur("openrouter", "x/unknown", 1, 1)


def _broken(change: str) -> dict[str, Any]:
    data = _valid()
    if change == "unmapped role":
        del data["roles"]["judge"]
    elif change == "unknown role":
        data["roles"]["poet"] = {"provider": "openrouter", "model": "a/cheap"}
    elif change == "unknown provider":
        data["roles"]["facts"] = {"provider": "ollama", "model": "a/cheap"}
    elif change == "role model without price":
        data["roles"]["facts"] = {"provider": "openrouter", "model": "a/dear"}
    elif change == "contract model without price":
        data["contract_models"]["meta"] = "m-wonder"
    elif change == "missing contract provider":
        del data["contract_models"]["gemini"]
    elif change == "timeout above 180":
        data["timeout_seconds"] = 181
    elif change == "timeout zero":
        data["timeout_seconds"] = 0
    elif change == "negative price":
        data["prices"]["openrouter"]["a/cheap"]["input"] = -1
    elif change == "rate zero":
        data["eur_per_usd"] = 0
    elif change == "unknown key":
        data["temperature"] = 0.2
    return data


@pytest.mark.parametrize(
    "change",
    [
        "unmapped role",
        "unknown role",
        "unknown provider",
        "role model without price",
        "contract model without price",
        "missing contract provider",
        "timeout above 180",
        "timeout zero",
        "negative price",
        "rate zero",
        "unknown key",
    ],
)
def test_broken_config_is_refused(tmp_path: Path, change: str) -> None:
    with pytest.raises(ModelConfigError):
        load_models_config(_write(tmp_path, _broken(change)))


def test_missing_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ModelConfigError, match="not found"):
        load_models_config(tmp_path / "nope.yaml")


def test_packaged_default_loads_and_is_package_data() -> None:
    assert DEFAULT_MODELS_FILE.name == "models.yaml"
    assert DEFAULT_MODELS_FILE.parent.name == "models"
    config = load_models_config(DEFAULT_MODELS_FILE)
    assert isinstance(config, ModelsConfig)
    assert config.timeout_seconds <= 180
    # OpenRouter is the default route for every role (AGENTS.md, model rules).
    assert {config.roles[role].provider for role in ROLES} == {"openrouter"}


def test_settings_default_to_replay_and_packaged_file(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MKC_MODEL_MODE", "MKC_MODELS_FILE", "MKC_MODEL_REPLAY_DIR"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.model_mode == "replay"
    assert settings.models_file == ""
    assert settings.model_replay_dir == ""


def test_settings_api_keys_are_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {
        "MKC_OPENROUTER_API_KEY": "openrouter_api_key",
        "MKC_GOOGLE_API_KEY": "google_api_key",
        "MKC_ANTHROPIC_API_KEY": "anthropic_api_key",
        "MKC_META_API_KEY": "meta_api_key",
    }
    for env in names:
        monkeypatch.setenv(env, f"value-of-{env}")
    settings = Settings()
    for env, field in names.items():
        secret = getattr(settings, field)
        assert secret.get_secret_value() == f"value-of-{env}"
        assert f"value-of-{env}" not in repr(settings)


def test_settings_refuse_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_MODEL_MODE", "maybe")
    with pytest.raises(ValueError):
        Settings()


def test_env_example_lists_the_model_settings() -> None:
    text = (Path(__file__).resolve().parents[3] / ".env.example").read_text(encoding="utf-8")
    for name in (
        "MKC_MODEL_MODE=",
        "MKC_MODELS_FILE=",
        "MKC_MODEL_REPLAY_DIR=",
        "MKC_OPENROUTER_API_KEY=",
        "MKC_GOOGLE_API_KEY=",
        "MKC_ANTHROPIC_API_KEY=",
        "MKC_META_API_KEY=",
    ):
        assert f"\n{name}\n" in text
