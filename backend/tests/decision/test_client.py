"""MKC-46: `DecisionClient` asks Noul and Choice questions in one request and parses the
answers into our own typed answers (offline, with a fake decision model).

The pinned interface is in `handoff/lane-c.md`. `mkc.decision` is imported inside each test,
so every test fails on its own until the package exists.
"""

import importlib
from types import ModuleType
from typing import Any

import pytest
from langchain_core.decisions import Choice, Noul

from tests.decision.fakes import FakeDecisionModel, choice, noul, response

STATE = "Synthetic household site: one PV system (9.8 kWp), one heat pump, one meter."


def _client() -> ModuleType:
    return importlib.import_module("mkc.decision.client")


def _types() -> ModuleType:
    return importlib.import_module("mkc.decision.types")


def _spike_questions() -> dict[str, Any]:
    """Three Noul and one Choice question, as in the ticket's test."""
    t = _types()
    return {
        "has_pv": t.NoulQuestion(instructions="Does the site have a PV system?"),
        "has_heat_pump": t.NoulQuestion(
            instructions="Does the site have a heat pump?",
            yes="A heat pump is named.",
            no="No heat pump is named.",
        ),
        "has_wallbox": t.NoulQuestion(instructions="Does the site have a wallbox?"),
        "scope": t.ChoiceQuestion(
            instructions="Which customer segment is this site?",
            criteria={
                "household": "A private household.",
                "commercial": "A business on low voltage.",
                "medium_voltage": "A site on medium voltage.",
            },
        ),
    }


def _spike_answers() -> dict[str, Any]:
    return response(
        {
            "has_pv": noul(0.97),
            "has_heat_pump": noul(0.91),
            "has_wallbox": noul(0.04),
            "scope": choice(
                "household",
                {"household": 0.88, "commercial": 0.1, "medium_voltage": 0.02},
                0.8,
            ),
        }
    )


def _decide(body: dict[str, Any], questions: dict[str, Any]) -> tuple[Any, FakeDecisionModel]:
    model = FakeDecisionModel(body=body)
    return _client().DecisionClient(model).decide(STATE, questions), model


# --- one request, typed answers ---------------------------------------------------------


def test_three_nouls_and_one_choice_are_parsed_into_typed_answers() -> None:
    t = _types()
    decisions, _ = _decide(_spike_answers(), _spike_questions())
    assert isinstance(decisions, t.Decisions)
    assert set(decisions.nouls) == {"has_pv", "has_heat_pump", "has_wallbox"}
    assert all(isinstance(a, t.NoulAnswer) for a in decisions.nouls.values())
    assert decisions.nouls["has_pv"].probability == pytest.approx(0.97)
    assert decisions.nouls["has_wallbox"].probability == pytest.approx(0.04)
    answer = decisions.choices["scope"]
    assert isinstance(answer, t.ChoiceAnswer)
    assert answer.choice == "household"
    assert answer.probabilities == pytest.approx(
        {"household": 0.88, "commercial": 0.1, "medium_voltage": 0.02}
    )
    assert answer.confidence == pytest.approx(0.8)
    assert decisions.model_id == "jev-1.13.0"


def test_all_questions_go_in_one_request() -> None:
    _, model = _decide(_spike_answers(), _spike_questions())
    assert len(model.seen) == 1
    state, questions = model.seen[0]
    assert state == STATE
    assert set(questions) == {"has_pv", "has_heat_pump", "has_wallbox", "scope"}


def test_questions_are_sent_as_noul_and_choice() -> None:
    _, model = _decide(_spike_answers(), _spike_questions())
    sent = model.seen[0][1]
    assert isinstance(sent["has_pv"], Noul)
    assert sent["has_pv"].instructions == "Does the site have a PV system?"
    assert sent["has_pv"].criteria is None
    assert isinstance(sent["scope"], Choice)
    assert set(sent["scope"].criteria) == {"household", "commercial", "medium_voltage"}


def test_noul_yes_and_no_become_the_criteria() -> None:
    _, model = _decide(_spike_answers(), _spike_questions())
    criteria = model.seen[0][1]["has_heat_pump"].criteria
    assert criteria.true == "A heat pump is named."
    assert criteria.false == "No heat pump is named."


def test_callers_never_see_langchain_answer_types() -> None:
    from langchain_core.decisions import ChoiceAnswer, NoulAnswer

    decisions, _ = _decide(_spike_answers(), _spike_questions())
    assert not isinstance(decisions.nouls["has_pv"], NoulAnswer)
    assert not isinstance(decisions.choices["scope"], ChoiceAnswer)


def test_typed_answers_are_frozen() -> None:
    decisions, _ = _decide(_spike_answers(), _spike_questions())
    with pytest.raises((TypeError, ValueError)):
        decisions.nouls["has_pv"].probability = 0.5


# --- bad requests and bad responses -----------------------------------------------------


def test_no_questions_is_refused() -> None:
    with pytest.raises(ValueError, match="question"):
        _decide(_spike_answers(), {})


def test_more_than_32_questions_is_refused() -> None:
    t = _types()
    questions = {f"q{i}": t.NoulQuestion(instructions=f"Question {i}?") for i in range(33)}
    with pytest.raises(ValueError, match="32"):
        _decide(_spike_answers(), questions)


def test_32_questions_are_accepted() -> None:
    t = _types()
    questions = {f"q{i}": t.NoulQuestion(instructions=f"Question {i}?") for i in range(32)}
    body = response({f"q{i}": noul(0.5) for i in range(32)})
    decisions, _ = _decide(body, questions)
    assert len(decisions.nouls) == 32


def test_a_missing_answer_is_a_decision_error() -> None:
    t = _types()
    body = _spike_answers()
    del body["answers"]["has_wallbox"]
    with pytest.raises(t.DecisionError, match="has_wallbox"):
        _decide(body, _spike_questions())


def test_an_answer_of_the_wrong_type_is_a_decision_error() -> None:
    t = _types()
    body = _spike_answers()
    body["answers"]["scope"] = noul(0.5)
    with pytest.raises(t.DecisionError, match="scope"):
        _decide(body, _spike_questions())


def test_a_choice_outside_the_criteria_is_a_decision_error() -> None:
    t = _types()
    body = _spike_answers()
    body["answers"]["scope"] = choice("off_topic", {"off_topic": 1.0}, 1.0)
    with pytest.raises(t.DecisionError, match="off_topic"):
        _decide(body, _spike_questions())


def test_a_choice_question_needs_two_labels() -> None:
    t = _types()
    with pytest.raises(ValueError):
        t.ChoiceQuestion(instructions="Which one?", criteria={"only": "The only label."})


def test_decision_error_is_a_model_error() -> None:
    """The harness treats it like any other failed model call (MKC-18)."""
    from mkc.models.types import ModelError

    assert issubclass(_types().DecisionError, ModelError)
