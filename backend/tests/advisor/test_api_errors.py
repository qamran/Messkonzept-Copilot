"""MKC-36.3, development agent: model errors, the real `get_model_client`, the length limit.

The test agent's `test_api.py` pins the routes; these cover the error paths it leaves open.
"""

import pytest
from fastapi import HTTPException

from mkc.advisor.api import get_model_client
from mkc.advisor.facts import MAX_TEXT_CHARS
from mkc.config import Settings
from mkc.models.client import ModelClient
from mkc.models.types import ModelError
from tests.advisor.fakes import household
from tests.advisor.test_api import Setup, _auth


def test_model_error_is_a_503_without_details(setup: Setup, token: str) -> None:
    api, model = setup(household())
    model.error = ModelError("provider said: secret detail")

    response = api.post(
        "/api/advisor/facts", json={"text": "EFH", "operator_id": "x"}, headers=_auth(token)
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The fact extraction is unavailable"}


def test_text_at_the_limit_is_accepted(setup: Setup, token: str) -> None:
    api, model = setup(household())
    text = "a" * MAX_TEXT_CHARS

    response = api.post(
        "/api/advisor/facts", json={"text": text, "operator_id": "x"}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert len(model.seen) == 1


def test_get_model_client_builds_the_configured_client() -> None:
    client = get_model_client(Settings(model_mode="live"))
    assert isinstance(client, ModelClient)


def test_get_model_client_without_a_replay_store_is_a_503() -> None:
    with pytest.raises(HTTPException) as caught:
        get_model_client(Settings(model_mode="replay", model_replay_dir=""))
    assert caught.value.status_code == 503
    assert caught.value.detail == "The fact extraction is unavailable"
