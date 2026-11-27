"""Our own decision types (MKC-46): callers of the decision layer never see LangChain types.

A question is a Noul (yes/no, answered with a probability of yes) or a Choice (one label out
of at least two, answered with the distribution and a confidence). `Decisions` holds the
answers of one request, keyed by question id.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mkc.models.types import ModelError

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class NoulQuestion(BaseModel):
    """A yes/no question. `yes` and `no` say what each outcome means; empty = not given."""

    model_config = _FROZEN

    instructions: str = Field(min_length=1)
    yes: str = ""
    no: str = ""


class ChoiceQuestion(BaseModel):
    """Pick one label; `criteria` maps each label to what it means (at least two labels)."""

    model_config = _FROZEN

    instructions: str = Field(min_length=1)
    criteria: dict[str, str]

    @field_validator("criteria")
    @classmethod
    def _two_labels(cls, criteria: dict[str, str]) -> dict[str, str]:
        if len(criteria) < 2:
            raise ValueError("a choice question needs at least two labels")
        return criteria


class NoulAnswer(BaseModel):
    """The probability that the answer is yes."""

    model_config = _FROZEN

    probability: float = Field(ge=0.0, le=1.0)


class ChoiceAnswer(BaseModel):
    """The chosen label, the distribution over the labels, and how concentrated it is
    (`confidence` is not the chosen label's probability)."""

    model_config = _FROZEN

    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)


class Decisions(BaseModel):
    """The answers of one request, keyed by question id; `model_id` is the model that
    answered (thresholds are pinned per model id, ADR 004)."""

    model_config = _FROZEN

    nouls: dict[str, NoulAnswer]
    choices: dict[str, ChoiceAnswer]
    model_id: str


class DecisionError(ModelError):
    """The decision model's reply does not answer the questions asked: an answer is missing,
    of the wrong type, or a label outside the criteria. The item fails like any other model
    error (MKC-18)."""
