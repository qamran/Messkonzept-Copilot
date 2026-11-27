"""Advisor routes (MKC-36): site facts from free text and the follow-up questions.

Any signed-in user may call them; the routes are plain `def` because the model call blocks.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from mkc.advisor.facts import MAX_TEXT_CHARS, SiteFacts, extract_facts
from mkc.advisor.questions import Question, required_questions
from mkc.api.auth import User, require_user
from mkc.config import Settings, get_settings
from mkc.models.client import ModelClient
from mkc.models.types import ModelError

log = logging.getLogger("mkc.advisor")

UNAVAILABLE = "The fact extraction is unavailable"

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class FactsRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    operator_id: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, text: str) -> str:
        if not text.strip():
            raise ValueError("the site description is empty")
        return text


def _unavailable(error: ModelError) -> HTTPException:
    # The class name only: provider messages can carry request details.
    log.error("advisor model call failed: %s", type(error).__name__)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE)


def get_model_client(settings: Annotated[Settings, Depends(get_settings)]) -> ModelClient:
    """FastAPI dependency: the configured client (tests replace it); 503 if misconfigured."""
    try:
        return ModelClient.from_settings(settings)
    except ModelError as error:
        raise _unavailable(error) from None


@router.post("/facts")
def facts(
    body: FactsRequest,
    _user: Annotated[User, Depends(require_user)],
    client: Annotated[ModelClient, Depends(get_model_client)],
) -> SiteFacts:
    try:
        return extract_facts(body.text, body.operator_id, client)
    except ModelError as error:
        raise _unavailable(error) from None


@router.post("/questions")
def questions(body: SiteFacts, _user: Annotated[User, Depends(require_user)]) -> list[Question]:
    return required_questions(body)
