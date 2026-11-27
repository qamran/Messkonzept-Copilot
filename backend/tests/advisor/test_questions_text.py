"""MKC-36.2, development agent: every question's text, options and order.

The test agent's `test_questions.py` pins which fields are asked; these pin what is asked.
"""

from mkc.advisor.facts import Battery, Pv, SiteFacts, Sve
from mkc.advisor.questions import Question, required_questions


def _all_gaps() -> SiteFacts:
    """A household where every result-changing fact is missing."""
    return SiteFacts(
        operator_id="x",
        pv=Pv(kwp=None, feed_in=None, generation_metered=None),
        battery=Battery(present=True, inverter=None),
        sve=[Sve(type="heat_pump", modul14a=None)],
        extra_households=None,
        unknown=[
            "extra_households",
            "pv.generation_metered",
            "pv.kwp",
            "sve.modul14a",
            "battery.inverter",
            "pv.feed_in",
        ],
    )


def test_questions_come_in_a_fixed_order_with_their_options() -> None:
    questions = required_questions(_all_gaps())

    assert [(q.field, q.options) for q in questions] == [
        ("pv.feed_in", ["surplus", "full"]),
        ("pv.generation_metered", ["yes", "no"]),
        ("battery.inverter", ["shared", "separate"]),
        ("sve.modul14a", ["1", "2"]),
        ("extra_households", []),
    ]
    assert all(q.text.endswith("?") for q in questions)
    assert len({q.text for q in questions}) == len(questions)


def test_battery_presence_asked_only_without_battery_facts() -> None:
    asked = required_questions(SiteFacts(operator_id="x", unknown=["battery.present"]))
    assert [(q.field, q.options) for q in asked] == [("battery.present", ["yes", "no"])]

    known = SiteFacts(operator_id="x", battery=Battery(present=False), unknown=["battery.present"])
    assert required_questions(known) == []


def test_a_known_value_is_not_asked_even_if_listed_unknown() -> None:
    facts = SiteFacts(
        operator_id="x",
        pv=Pv(kwp=5.0, feed_in="full", generation_metered=True),
        battery=Battery(present=True, inverter="separate"),
        sve=[Sve(type="wallbox", modul14a=1)],
        extra_households=2,
        unknown=[
            "pv.feed_in",
            "pv.generation_metered",
            "battery.inverter",
            "sve.modul14a",
            "extra_households",
        ],
    )
    assert required_questions(facts) == []


def test_generation_meter_and_households_asked_only_when_listed() -> None:
    facts = SiteFacts(
        operator_id="x",
        pv=Pv(kwp=5.0, feed_in="full", generation_metered=None),
        extra_households=None,
    )
    assert required_questions(facts) == []


def test_module_asked_once_for_several_sves() -> None:
    facts = SiteFacts(
        operator_id="x",
        sve=[Sve(type="heat_pump", modul14a=None), Sve(type="wallbox", modul14a=None)],
    )
    assert [q.field for q in required_questions(facts)] == ["sve.modul14a"]


def test_question_is_a_plain_model() -> None:
    q = Question(field="pv.feed_in", text="?", options=[])
    assert q.model_dump() == {"field": "pv.feed_in", "text": "?", "options": []}
