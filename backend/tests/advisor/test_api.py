"""MKC-36: `POST /api/advisor/facts` and `POST /api/advisor/questions` (signed-in users).

The model client comes from the `get_model_client` dependency, which the tests replace with a
real `ModelClient` over a fake chat model. Keys are generated at runtime; no network, no DB.
"""

import time
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mkc.advisor.api import get_model_client
from mkc.advisor.facts import MAX_TEXT_CHARS
from mkc.api.app import create_app
from mkc.config import Settings
from tests.advisor.fakes import facts_client, household
from tests.models.fakes import FakeChatModel

ISSUER = "https://example-instance.clerk.accounts.dev"
ORIGIN = "http://localhost:5173"
TEXT = "EFH, 10 kWp PV Überschuss, Batterie am gleichen Wechselrichter, Wärmepumpe Modul 2"


@pytest.fixture(scope="module")
def key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def token(key: rsa.RSAPrivateKey) -> str:
    """A signed-in user without the admin role."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user_1",
        "iss": ISSUER,
        "azp": ORIGIN,
        "iat": now,
        "nbf": now - 5,
        "exp": now + 60,
        "role": "",
    }
    return jwt.encode(claims, key, algorithm="RS256")


Setup = Callable[[dict[str, Any]], tuple[TestClient, FakeChatModel]]


@pytest.fixture
def setup(key: rsa.RSAPrivateKey) -> Iterator[Setup]:
    apps: list[FastAPI] = []

    def make(parsed: dict[str, Any]) -> tuple[TestClient, FakeChatModel]:
        settings = Settings(clerk_issuer=ISSUER, clerk_authorized_parties=[ORIGIN])
        public_key = key.public_key()
        app = create_app(settings, key_resolver=lambda _token: public_key)
        client, model = facts_client(parsed)
        app.dependency_overrides[get_model_client] = lambda: client
        apps.append(app)
        return TestClient(app), model

    yield make
    for app in apps:
        app.dependency_overrides.clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_facts_route_returns_site_facts(setup: Setup, token: str) -> None:
    api, model = setup(household())

    response = api.post(
        "/api/advisor/facts",
        json={"text": TEXT, "operator_id": "stromnetz-berlin"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operator_id"] == "stromnetz-berlin"
    assert body["pv"]["feed_in"] == "surplus"
    assert body["battery"] == {"present": True, "inverter": "shared"}
    assert body["sve"] == [{"type": "heat_pump", "modul14a": 2}]
    assert body["out_of_scope"] == []
    assert len(model.seen) == 1


def test_facts_route_needs_a_signed_in_user(setup: Setup) -> None:
    api, model = setup(household())

    response = api.post("/api/advisor/facts", json={"text": TEXT, "operator_id": "x"})

    assert response.status_code == 401
    assert model.seen == []


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_input_rejected_by_the_route(setup: Setup, token: str, text: str) -> None:
    api, model = setup(household())

    response = api.post(
        "/api/advisor/facts", json={"text": text, "operator_id": "x"}, headers=_auth(token)
    )

    assert response.status_code == 422
    assert model.seen == []


def test_too_long_input_rejected(setup: Setup, token: str) -> None:
    api, model = setup(household())
    text = "a" * (MAX_TEXT_CHARS + 1)

    response = api.post(
        "/api/advisor/facts", json={"text": text, "operator_id": "x"}, headers=_auth(token)
    )

    assert response.status_code == 422
    assert model.seen == []


def test_empty_operator_rejected(setup: Setup, token: str) -> None:
    api, model = setup(household())
    response = api.post(
        "/api/advisor/facts", json={"text": TEXT, "operator_id": ""}, headers=_auth(token)
    )
    assert response.status_code == 422
    assert model.seen == []


def test_modul3_answered_as_out_of_scope_by_the_route(setup: Setup, token: str) -> None:
    api, _model = setup(household(sve=[{"type": "heat_pump", "modul14a": 3}]))

    response = api.post(
        "/api/advisor/facts", json={"text": TEXT, "operator_id": "x"}, headers=_auth(token)
    )

    assert response.status_code == 200
    notes = response.json()["out_of_scope"]
    assert [n["reason"] for n in notes] == ["modul3"]
    assert "operator" in notes[0]["message"].lower()


def test_questions_route_asks_only_result_changing_gaps(setup: Setup, token: str) -> None:
    api, model = setup(household())
    facts = {
        "operator_id": "x",
        "pv": {"kwp": None, "feed_in": "surplus", "generation_metered": None},
        "battery": {"present": True, "inverter": None},
        "sve": [{"type": "heat_pump", "modul14a": 2}],
        "extra_households": 0,
        "unknown": ["pv.kwp", "pv.generation_metered", "battery.inverter"],
        "out_of_scope": [],
    }

    response = api.post("/api/advisor/questions", json=facts, headers=_auth(token))

    assert response.status_code == 200
    assert {q["field"] for q in response.json()} == {"pv.generation_metered", "battery.inverter"}
    assert model.seen == []  # plain code, no model call


def test_questions_route_needs_a_signed_in_user(setup: Setup) -> None:
    api, _model = setup(household())
    response = api.post("/api/advisor/questions", json={"operator_id": "x"})
    assert response.status_code == 401


def test_questions_route_rejects_modul3_facts(setup: Setup, token: str) -> None:
    api, _model = setup(household())
    facts = {"operator_id": "x", "sve": [{"type": "heat_pump", "modul14a": 3}]}
    response = api.post("/api/advisor/questions", json=facts, headers=_auth(token))
    assert response.status_code == 422
