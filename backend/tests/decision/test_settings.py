"""MKC-46: "The LLM fallback stays the default until this passes" (ADR 004, decision 27).

`MKC_DECISION_BACKEND=jev|llm` (backlog, MKC-47) picks the decision backend; it defaults to
`llm`, the structured-output fallback. `MKC_DECISION_MODEL` is the Jev model on OpenRouter.
"""

import pytest
from pydantic import ValidationError

from mkc.config import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MKC_DECISION_BACKEND", raising=False)
    monkeypatch.delenv("MKC_DECISION_MODEL", raising=False)


def test_decision_backend_defaults_to_the_llm_fallback() -> None:
    assert Settings().decision_backend == "llm"


def test_decision_backend_jev_is_set_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MKC_DECISION_BACKEND", "jev")
    assert Settings().decision_backend == "jev"


def test_an_empty_decision_backend_means_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_DECISION_BACKEND", "")
    assert Settings().decision_backend == "llm"


@pytest.mark.parametrize("value", ["typesafe", "JEV ", "gpt"])
def test_an_unknown_decision_backend_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MKC_DECISION_BACKEND", value)
    with pytest.raises(ValidationError):
        Settings()


def test_decision_model_defaults_to_jev_latest_on_openrouter() -> None:
    assert Settings().decision_model == "~typesafe/jev-latest"
