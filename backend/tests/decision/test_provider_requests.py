"""MKC-46.1: what the decision model sends (development agent; offline, mock transport).

The spike (27.11.2026) found the working path: `{base_url}/v1/systemone` with base URL
`https://openrouter.ai/api`. OpenRouter serves it for the TypeSafe SDKs and honours the
`provider` routing preferences in the body, so every request carries our zero-data-retention
routing, as every chat model does (`OPENROUTER_ROUTING`).
"""

import json
from typing import Any

import httpx2
from langchain_core.decisions import Noul
from pydantic import SecretStr

from mkc.config import Settings
from mkc.models.providers import OPENROUTER_ROUTING, build_decision_model

BODY = {
    "model": "typesafe/jev-1.14-20261014",
    "answers": {"has_pv": {"type": "noul", "noul": 0.98}},
    "usage": {"input_tokens": 283, "output_tokens": 22, "cost": 0.000011886},
    "id": "gen-dec-1",
    "provider": "TypeSafe",
}


def _send() -> tuple[httpx2.Request, Any]:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=BODY)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    settings = Settings(openrouter_api_key=SecretStr("or-key"))
    model = build_decision_model(settings, http_client=client)
    response = model.invoke(
        {"state": "Synthetic site.", "questions": {"has_pv": Noul(instructions="PV?")}}
    )
    assert len(seen) == 1
    return seen[0], response


def test_the_request_goes_to_the_openrouter_system_one_path() -> None:
    request, _ = _send()
    assert str(request.url) == "https://openrouter.ai/api/v1/systemone"
    assert request.method == "POST"


def test_the_request_carries_our_key() -> None:
    request, _ = _send()
    assert request.headers["authorization"] == "Bearer or-key"


def test_the_request_asks_for_zero_data_retention_routing() -> None:
    request, _ = _send()
    body = json.loads(request.content)
    assert body["provider"] == OPENROUTER_ROUTING
    assert body["model"] == "~typesafe/jev-latest"
    assert body["questions"]["has_pv"]["type"] == "noul"


def test_openrouter_extra_response_fields_are_tolerated() -> None:
    _, response = _send()
    assert response.nouls["has_pv"].noul == 0.98
    assert response.model == "typesafe/jev-1.14-20261014"
