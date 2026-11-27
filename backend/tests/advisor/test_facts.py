"""MKC-36: free text becomes `SiteFacts` (feature 51, design sections 7 and 9).

The model answers with `FactsExtraction` (it may say Modul 3, a plug-in PV or a commercial
site); the code maps that to `SiteFacts`, whose `modul14a` is only 1 or 2. Out-of-scope input
is answered with a "not covered, clarify with the operator" note and no facts (Review Focus 2).
"""

from typing import Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from mkc.advisor.facts import EmptyInputError, SiteFacts, Sve, extract_facts
from tests.advisor.fakes import facts_client, household

OPERATOR = "stromnetz-berlin"
GERMAN = "EFH in Dresden, 10 kWp PV Überschuss, Batterie am gleichen Wechselrichter, WP Modul 2"


def _extract(text: str, parsed: dict[str, Any]) -> SiteFacts:
    client, _model = facts_client(parsed)
    return extract_facts(text, OPERATOR, client)


def _assert_not_covered(facts: SiteFacts, reason: str) -> None:
    assert [note.reason for note in facts.out_of_scope] == [reason]
    assert "operator" in facts.out_of_scope[0].message.lower()
    # Never a forced match: no facts are carried through and nothing is asked.
    assert facts.pv is None
    assert facts.battery is None
    assert facts.sve == []
    assert facts.extra_households is None
    assert facts.unknown == []


def test_extracts_pv_battery_heatpump_modul2() -> None:
    client, model = facts_client(household())

    facts = extract_facts(GERMAN, OPERATOR, client)

    assert facts.operator_id == OPERATOR
    assert facts.pv is not None
    assert facts.pv.kwp == 10.0
    assert facts.pv.feed_in == "surplus"
    assert facts.battery is not None
    assert facts.battery.present is True
    assert facts.battery.inverter == "shared"
    assert [(s.type, s.modul14a) for s in facts.sve] == [("heat_pump", 2)]
    assert facts.extra_households == 0
    assert facts.out_of_scope == []
    assert len(model.seen) == 1


def test_user_text_is_sent_as_data_in_a_user_message() -> None:
    client, model = facts_client(household())

    extract_facts(GERMAN, OPERATOR, client)

    (messages,) = model.seen
    assert any(isinstance(m, HumanMessage) and GERMAN in str(m.content) for m in messages)
    assert not any(isinstance(m, SystemMessage) and GERMAN in str(m.content) for m in messages)


def test_operator_id_is_opaque_and_echoed() -> None:
    client, _model = facts_client(household())
    facts = extract_facts(GERMAN, "any-operator-42", client)
    assert facts.operator_id == "any-operator-42"


def test_unknown_keeps_only_known_fact_keys() -> None:
    facts = _extract(GERMAN, household(unknown=["pv.kwp", "roof.orientation", "battery.inverter"]))
    assert facts.unknown == ["pv.kwp", "battery.inverter"]


def test_english_input_handled() -> None:
    text = "Single-family house, 8 kWp PV full feed-in, wallbox under 14a module 1, no battery"
    parsed = household(
        pv={"kwp": 8.0, "feed_in": "full", "generation_metered": None, "plug_in": False},
        battery={"present": False, "inverter": None},
        sve=[{"type": "wallbox", "modul14a": 1}],
    )
    client, model = facts_client(parsed)

    facts = extract_facts(text, OPERATOR, client)

    assert facts.out_of_scope == []
    assert facts.pv is not None and facts.pv.feed_in == "full"
    assert facts.battery is not None and facts.battery.present is False
    assert [(s.type, s.modul14a) for s in facts.sve] == [("wallbox", 1)]
    assert len(model.seen) == 1


def test_plugin_pv_out_of_scope() -> None:
    parsed = household(
        pv={"kwp": 0.8, "feed_in": "surplus", "generation_metered": None, "plug_in": True},
        battery=None,
        sve=[],
    )
    _assert_not_covered(_extract("Balkonkraftwerk 800 W an der Steckdose", parsed), "plug_in_pv")


def test_commercial_site_out_of_scope() -> None:
    parsed = household(site_kind="commercial")
    text = "Bäckerei mit 30 kWp PV und Kühlhaus"
    _assert_not_covered(_extract(text, parsed), "commercial")


def test_medium_voltage_site_out_of_scope() -> None:
    _assert_not_covered(
        _extract("Anschluss in Mittelspannung", household(site_kind="medium_voltage")),
        "medium_voltage",
    )


def test_off_topic_input_out_of_scope() -> None:
    _assert_not_covered(
        _extract("Wie wird das Wetter morgen?", household(site_kind="off_topic")), "off_topic"
    )


def test_modul3_answered_as_out_of_scope() -> None:
    parsed = household(sve=[{"type": "heat_pump", "modul14a": 3}])
    _assert_not_covered(_extract("EFH, Wärmepumpe mit Modul 3", parsed), "modul3")


def test_site_facts_reject_modul3() -> None:
    with pytest.raises(ValidationError):
        Sve(type="heat_pump", modul14a=3)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_input_rejected(text: str) -> None:
    client, model = facts_client(household())

    with pytest.raises(EmptyInputError):
        extract_facts(text, OPERATOR, client)

    assert model.seen == []


def test_empty_input_error_is_a_value_error() -> None:
    assert issubclass(EmptyInputError, ValueError)
