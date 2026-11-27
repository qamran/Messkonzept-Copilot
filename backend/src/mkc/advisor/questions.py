"""Follow-up questions only for missing facts that change the result (MKC-36, feature 52).

Plain code, no model call. The result-changing facts are those design section 9 names: the
feed-in, a separate generation meter, whether there is a battery and on which inverter, the
§14a module, further households. The PV size alone is never asked.
"""

from collections.abc import Callable

from pydantic import BaseModel

from mkc.advisor.facts import FactKey, SiteFacts


class Question(BaseModel):
    field: FactKey
    text: str
    options: list[str]


# Each entry: the question, its options, and when it is asked. A missing value of the first
# kind (feed-in, inverter, module) is always asked; the others only when the model listed the
# key as unknown. A fact whose parent is absent (no PV, no battery, no SVE) is never asked.
Asked = Callable[[SiteFacts, bool], bool]

QUESTIONS: list[tuple[FactKey, str, list[str], Asked]] = [
    (
        "pv.feed_in",
        "Does the PV system feed in only the surplus or all of its generation?",
        ["surplus", "full"],
        lambda f, _listed: f.pv is not None and f.pv.feed_in is None,
    ),
    (
        "pv.generation_metered",
        "Should the PV generation be measured by a meter of its own?",
        ["yes", "no"],
        lambda f, listed: listed and f.pv is not None and f.pv.generation_metered is None,
    ),
    (
        "battery.present",
        "Is there a battery storage system?",
        ["yes", "no"],
        lambda f, listed: listed and f.battery is None,
    ),
    (
        "battery.inverter",
        "Is the battery on the PV inverter or on its own inverter?",
        ["shared", "separate"],
        lambda f, _listed: (
            f.battery is not None and f.battery.present and f.battery.inverter is None
        ),
    ),
    (
        "sve.modul14a",
        "Which §14a module applies to the controllable consumer, Modul 1 or Modul 2?",
        ["1", "2"],
        lambda f, _listed: any(s.modul14a is None for s in f.sve),
    ),
    (
        "extra_households",
        "How many further households share the grid connection?",
        [],
        lambda f, listed: listed and f.extra_households is None,
    ),
]


def required_questions(facts: SiteFacts) -> list[Question]:
    """The questions to ask before matching; none for an out-of-scope site."""
    if facts.out_of_scope:
        return []
    listed = set(facts.unknown)
    return [
        Question(field=key, text=text, options=list(options))
        for key, text, options, asked in QUESTIONS
        if asked(facts, key in listed)
    ]
