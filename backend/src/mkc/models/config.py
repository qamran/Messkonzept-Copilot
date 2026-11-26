"""Role → provider/model mapping and the price table, read from `models.yaml` (MKC-13.2)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mkc.models.types import PROVIDERS, ROLES, ModelConfigError, Provider, Role

DEFAULT_MODELS_FILE = Path(__file__).with_name("models.yaml")
"""Package data, so the backend image carries it."""

MAX_TIMEOUT_SECONDS = 180.0
"""Decision 42: a model call must fit the worker's 300 s turn budget."""


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RoleModel(_Strict):
    provider: Provider
    model: str = Field(min_length=1)


class Price(_Strict):
    """USD per million tokens."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)
    source: str = ""


class ModelsConfig(_Strict):
    eur_per_usd: float = Field(gt=0)
    timeout_seconds: float = Field(gt=0, le=MAX_TIMEOUT_SECONDS)
    roles: dict[Role, RoleModel]
    contract_models: dict[Provider, str]
    prices: dict[Provider, dict[str, Price]]

    @model_validator(mode="after")
    def _complete(self) -> "ModelsConfig":
        missing_roles = [role for role in ROLES if role not in self.roles]
        if missing_roles:
            raise ValueError(f"roles not mapped: {missing_roles}")
        missing = [p for p in PROVIDERS if p not in self.contract_models]
        if missing:
            raise ValueError(f"contract_models missing providers: {missing}")
        used = [(m.provider, m.model) for m in self.roles.values()]
        used += list(self.contract_models.items())
        unpriced = sorted({f"{p}:{m}" for p, m in used if m not in self.prices.get(p, {})})
        if unpriced:
            raise ValueError(f"no price for {unpriced}")
        return self

    def cost_eur(
        self, provider: Provider, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Cost of one call. A model without a price is an error, never cost 0."""
        price = self.prices.get(provider, {}).get(model)
        if price is None:
            raise ModelConfigError(f"no price for {provider}:{model}")
        usd = (input_tokens * price.input + output_tokens * price.output) / 1_000_000
        return usd * self.eur_per_usd


def load_models_config(path: Path = DEFAULT_MODELS_FILE) -> ModelsConfig:
    """Read and check `models.yaml`; every problem is a `ModelConfigError`."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ModelConfigError(f"models file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ModelConfigError(f"models file is not valid YAML: {path}: {error}") from error
    try:
        return ModelsConfig.model_validate(data)
    except ValidationError as error:
        raise ModelConfigError(f"models file {path} is invalid: {error}") from error
