"""MKC-36: follow-up questions only for missing facts that change the result (feature 52).

`required_questions(facts)` is plain code: no model call. The result-changing facts are the
ones design section 9 names (feed-in, battery inverter, generation meter, the §14a module,
an extra household); the PV size is not one of them for a household site.
"""

from typing import Any

from mkc.advisor.facts import Battery, Pv, ScopeNote, SiteFacts, Sve
from mkc.advisor.questions import Question, required_questions


def _facts(**overrides: Any) -> SiteFacts:
    """Complete household facts; nothing is missing."""
    fields: dict[str, Any] = {
        "operator_id": "stromnetz-berlin",
        "pv": Pv(kwp=10.0, feed_in="surplus", generation_metered=False),
        "battery": Battery(present=True, inverter="shared"),
        "sve": [Sve(type="heat_pump", modul14a=2)],
        "extra_households": 0,
        "unknown": [],
    }
    fields.update(overrides)
    return SiteFacts(**fields)


def _fields(questions: list[Question]) -> set[str]:
    return {q.field for q in questions}


def test_only_result_changing_unknowns_are_asked() -> None:
    facts = _facts(
        pv=Pv(kwp=None, feed_in="surplus", generation_metered=None),
        battery=Battery(present=True, inverter=None),
        unknown=["pv.kwp", "pv.generation_metered", "battery.inverter"],
    )

    questions = required_questions(facts)

    assert _fields(questions) == {"pv.generation_metered", "battery.inverter"}
    assert all(q.text.strip() for q in questions)


def test_complete_facts_need_no_questions() -> None:
    assert required_questions(_facts()) == []


def test_pv_size_alone_is_not_asked() -> None:
    facts = _facts(pv=Pv(kwp=None, feed_in="surplus", generation_metered=False), unknown=["pv.kwp"])
    assert required_questions(facts) == []


def test_missing_values_are_asked_even_when_not_listed_as_unknown() -> None:
    facts = _facts(
        pv=Pv(kwp=10.0, feed_in=None, generation_metered=False),
        battery=Battery(present=True, inverter=None),
        sve=[Sve(type="wallbox", modul14a=None)],
    )
    assert _fields(required_questions(facts)) == {"pv.feed_in", "battery.inverter", "sve.modul14a"}


def test_inverter_not_asked_without_a_battery() -> None:
    assert required_questions(_facts(battery=None, unknown=["battery.inverter"])) == []
    no_battery = _facts(battery=Battery(present=False, inverter=None), unknown=["battery.inverter"])
    assert required_questions(no_battery) == []


def test_pv_questions_not_asked_without_pv() -> None:
    facts = _facts(pv=None, unknown=["pv.feed_in", "pv.generation_metered"])
    assert required_questions(facts) == []


def test_module_not_asked_without_an_sve() -> None:
    assert required_questions(_facts(sve=[], unknown=["sve.modul14a"])) == []


def test_extra_household_asked_when_unknown() -> None:
    facts = _facts(extra_households=None, unknown=["extra_households"])
    assert _fields(required_questions(facts)) == {"extra_households"}


def test_each_field_asked_once() -> None:
    facts = _facts(battery=Battery(present=True, inverter=None), unknown=["battery.inverter"])
    assert [q.field for q in required_questions(facts)] == ["battery.inverter"]


def test_choice_questions_offer_the_allowed_values() -> None:
    facts = _facts(
        pv=Pv(kwp=10.0, feed_in=None, generation_metered=False),
        battery=Battery(present=True, inverter=None),
    )
    options = {q.field: q.options for q in required_questions(facts)}
    assert options["pv.feed_in"] == ["surplus", "full"]
    assert options["battery.inverter"] == ["shared", "separate"]


def test_out_of_scope_site_gets_no_questions() -> None:
    note = ScopeNote(reason="commercial", message="Not covered; clarify with the operator.")
    facts = SiteFacts(operator_id="stromnetz-berlin", unknown=["pv.feed_in"], out_of_scope=[note])
    assert required_questions(facts) == []


def test_out_of_scope_gaps_are_never_asked() -> None:
    # Gaps that would be asked for a household site; out of scope, nothing is asked.
    note = ScopeNote(reason="modul3", message="Not covered; clarify with the operator.")
    facts = _facts(
        pv=Pv(kwp=10.0, feed_in=None, generation_metered=None),
        battery=Battery(present=True, inverter=None),
        sve=[Sve(type="heat_pump", modul14a=None)],
        extra_households=None,
        unknown=["pv.generation_metered", "extra_households"],
        out_of_scope=[note],
    )
    assert required_questions(facts) == []
