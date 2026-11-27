"""A fake decision model for the decision-layer tests (no network, no key).

It is a `langchain_core.decisions.BaseDecisionModel`, the same base class as
`langchain_typesafe.TypeSafeClassifier`, so `DecisionClient` sees what it sees in production:
it replays one canned `ClassifierResponse` and records each request.
"""

from typing import Any

from langchain_core.decisions import BaseDecisionModel, ClassifierResponse
from pydantic import Field


class FakeDecisionModel(BaseDecisionModel):
    model: str = "~typesafe/jev-latest"
    body: dict[str, Any] = Field(default_factory=dict)
    seen: list[tuple[Any, dict[str, Any]]] = Field(default_factory=list)

    @property
    def _provider(self) -> str:
        return "fake"

    def _classify(self, state: Any, questions: dict[str, Any]) -> ClassifierResponse:
        self.seen.append((state, dict(questions)))
        return ClassifierResponse.model_validate(self.body)


def noul(probability: float) -> dict[str, Any]:
    return {"type": "noul", "noul": probability}


def choice(label: str, probabilities: dict[str, float], confidence: float) -> dict[str, Any]:
    return {
        "type": "choice",
        "choice": label,
        "probabilities": probabilities,
        "confidence": confidence,
    }


def response(answers: dict[str, dict[str, Any]], model: str = "jev-1.13.0") -> dict[str, Any]:
    return {"model": model, "answers": answers, "usage": {"input_tokens": 9, "output_tokens": 3}}
