"""`DecisionClient` (MKC-46): one request per call, typed answers back.

It takes any `langchain_core.decisions.BaseDecisionModel` (Jev on OpenRouter from
`mkc.models.providers.build_decision_model`, or a fake in tests) and imports no provider
package. Every question about one state goes in one request; the reply is checked against
the questions and converted into `mkc.decision.types`.
"""

from collections.abc import Mapping

from langchain_core.decisions import (
    BaseDecisionModel,
    Choice,
    ClassifierResponse,
    Noul,
    NoulCriteria,
    Question,
)
from langchain_core.decisions import ChoiceAnswer as LcChoiceAnswer
from langchain_core.decisions import NoulAnswer as LcNoulAnswer

from mkc.decision.types import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionError,
    Decisions,
    NoulAnswer,
    NoulQuestion,
)

MAX_QUESTIONS = 32
"""The most questions one request may carry (the decision API's limit)."""


class DecisionClient:
    def __init__(self, decision_model: BaseDecisionModel) -> None:
        self._model = decision_model

    def decide(
        self, state: str, questions: Mapping[str, NoulQuestion | ChoiceQuestion]
    ) -> Decisions:
        """Ask every question about `state` in one request."""
        if not questions:
            raise ValueError("a decision request needs at least one question")
        if len(questions) > MAX_QUESTIONS:
            raise ValueError(
                f"a decision request takes at most {MAX_QUESTIONS} questions, got {len(questions)}"
            )
        sent = {qid: _to_langchain(question) for qid, question in questions.items()}
        response = self._model.invoke({"state": state, "questions": sent})
        return _parse(response, questions)


def _to_langchain(question: NoulQuestion | ChoiceQuestion) -> Question:
    if isinstance(question, ChoiceQuestion):
        return Choice(instructions=question.instructions, criteria=dict(question.criteria))
    criteria = (
        NoulCriteria(true=question.yes, false=question.no) if question.yes or question.no else None
    )
    return Noul(instructions=question.instructions, criteria=criteria)


def _parse(
    response: ClassifierResponse, questions: Mapping[str, NoulQuestion | ChoiceQuestion]
) -> Decisions:
    nouls: dict[str, NoulAnswer] = {}
    choices: dict[str, ChoiceAnswer] = {}
    for qid, question in questions.items():
        answer = response.answers.get(qid)
        if answer is None:
            raise DecisionError(f"the decision model gave no answer to question {qid!r}")
        if isinstance(question, ChoiceQuestion):
            if not isinstance(answer, LcChoiceAnswer):
                raise DecisionError(
                    f"question {qid!r} asked for a choice, the answer is {answer.type!r}"
                )
            if answer.choice not in question.criteria:
                raise DecisionError(
                    f"question {qid!r}: the label {answer.choice!r} is not in the criteria"
                )
            choices[qid] = ChoiceAnswer(
                choice=answer.choice,
                probabilities=dict(answer.probabilities),
                confidence=answer.confidence,
            )
        else:
            if not isinstance(answer, LcNoulAnswer):
                raise DecisionError(
                    f"question {qid!r} asked for a noul, the answer is {answer.type!r}"
                )
            nouls[qid] = NoulAnswer(probability=answer.noul)
    return Decisions(nouls=nouls, choices=choices, model_id=response.model)
