"""MKC-36: a real `ModelClient` over a fake chat model that answers with one `FactsExtraction`.

The client validates the canned answer against the schema the code passes, as a real provider
reply would be, so a wrong schema in the code fails here too. No network, no key.
"""

from typing import Any

from mkc.models.client import ModelClient
from tests.models.fakes import FakeChatModel, ai, fake
from tests.models.test_client import Built, config

SCHEMA_NAME = "FactsExtraction"
"""The model-facing schema in `mkc.advisor.facts`; its class name is the tool name."""


def household(**overrides: Any) -> dict[str, Any]:
    """A household: 10 kWp PV surplus, battery on the same inverter, heat pump Modul 2."""
    parsed: dict[str, Any] = {
        "site_kind": "household",
        "pv": {"kwp": 10.0, "feed_in": "surplus", "generation_metered": None, "plug_in": False},
        "battery": {"present": True, "inverter": "shared"},
        "sve": [{"type": "heat_pump", "modul14a": 2}],
        "extra_households": 0,
        "unknown": [],
    }
    parsed.update(overrides)
    return parsed


def facts_client(parsed: dict[str, Any]) -> tuple[ModelClient, FakeChatModel]:
    """The client and its fake model; `model.seen` holds every request sent."""
    call = {"id": "facts-1", "name": SCHEMA_NAME, "args": parsed}
    model = fake(ai("", tool_calls=[call]))
    return ModelClient(config(), Built(model), mode="live"), model
