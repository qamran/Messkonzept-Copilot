"""MKC-46: the live spike. Three Noul questions and one Choice question go through
`langchain-typesafe` to Jev on OpenRouter (`~typesafe/jev-latest`) in one request, and the
reply is parsed into typed answers.

It spends real money (well under one cent) and needs `MKC_OPENROUTER_API_KEY`, so it is
deselected by default. Run it on purpose, with the coordinator's go:

    cd backend && uv run --env-file .env pytest -m live tests/decision/test_jev_live.py -v

The result goes into ADR 004 and the status doc: the working path, or the alternative.
"""

import pytest

from mkc.config import Settings

pytestmark = pytest.mark.live

STATE = (
    "Synthetic household site in Musterstadt: a single-family house with one PV system "
    "(9.8 kWp) and one heat pump, no wallbox, connected to the low-voltage grid."
)


def test_three_nouls_and_one_choice_round_trip_through_jev_on_openrouter() -> None:
    settings = Settings()
    if not settings.openrouter_api_key.get_secret_value():
        pytest.skip("no API key for openrouter")
    from mkc.decision.client import DecisionClient
    from mkc.decision.types import ChoiceAnswer, ChoiceQuestion, NoulAnswer, NoulQuestion

    labels = {
        "household": "A private household on low voltage.",
        "commercial": "A business on low voltage.",
        "medium_voltage": "A site connected to medium voltage.",
    }
    questions = {
        "has_pv": NoulQuestion(instructions="Does the site have a PV system?"),
        "has_heat_pump": NoulQuestion(instructions="Does the site have a heat pump?"),
        "has_wallbox": NoulQuestion(instructions="Does the site have a wallbox?"),
        "scope": ChoiceQuestion(instructions="Which segment is this site?", criteria=labels),
    }
    from mkc.models.providers import build_decision_model  # the factory, after the questions

    client = DecisionClient(build_decision_model(settings))
    decisions = client.decide(STATE, questions)

    assert set(decisions.nouls) == {"has_pv", "has_heat_pump", "has_wallbox"}
    for answer in decisions.nouls.values():
        assert isinstance(answer, NoulAnswer)
        assert 0.0 <= answer.probability <= 1.0
    scope = decisions.choices["scope"]
    assert isinstance(scope, ChoiceAnswer)
    assert scope.choice in labels
    assert set(scope.probabilities) <= set(labels)
    assert 0.0 <= scope.confidence <= 1.0
    assert decisions.model_id
