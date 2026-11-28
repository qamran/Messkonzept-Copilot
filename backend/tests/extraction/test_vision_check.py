"""MKC-25: the go/no-go vision check (feature 34, design 15): a small, tested module that reads
5 Berlin concepts with one vision call each and compares the topology with a truth sheet the
user filled in from the PDF before any call.

Pinned interface (module `mkc.extraction.vision_check`; everything else is the development
agent's):

    load_truth(path) -> list[dict]
        The truth sheet, YAML: `concepts:` a list of entries `{operator, concept, page,
        meters, components}`; `meters` a list of `{label, upstream}`, `components` a list of
        `{kind, attached_to}` (design 7 field names). `null` means "not filled in yet".
    compare(truth_entry, read) -> verdict with bool attributes `meters`, `upstream`,
        `components`. `read` has the same `meters` / `components` shape (extra keys such as
        `purpose` are ignored). Raises ValueError for an unfilled truth entry.
    check_concepts(client, pdf, truth, *, dpi) -> list[(concept, verdict)], in truth order.
        Finds each concept's region with the Berlin segmenter, renders it with
        `render_region`, sends ONE `ModelClient.vision` call (role `extract_vision`) and
        compares. Refuses an unfilled sheet before any model call.
    results_table(rows) -> str: the Markdown table for the status doc, header
        `| concept | meters correct | upstream correct | components correct |`, cells
        `yes` / `no`; `scripts/check_go_no_go.py` accepts it.
    `python -m mkc.extraction.vision_check --help` exits 0.

Comparison rule (coordinator ruling 4): per concept three booleans, each a set equality
after the same normalisation of both sides (strip, case-fold), so order and duplicates do not
matter. meters: the set of labels; upstream: the set of (label, upstream) pairs, a root meter's
upstream `null`; components: the set of (kind, attached_to) pairs.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import BaseMessage

from mkc.models.client import CallTrace, ModelClient
from mkc.models.replay import ReplayStore
from mkc.models.types import Provider
from tests.extraction.conftest import berlin_pages, make_pdf
from tests.harness.test_loop import config
from tests.models.fakes import FakeChatModel, ai

BACKEND = Path(__file__).resolve().parents[2]
DPI = 100

METERS = [
    {"label": "Z1", "upstream": None},
    {"label": "Z2", "upstream": "Z1"},
]
COMPONENTS = [{"kind": "G", "attached_to": "Z2"}, {"kind": "WR", "attached_to": "Z2"}]


def truth(concept: str = "3", page: int = 4, **change: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "operator": "stromnetz-berlin",
        "concept": concept,
        "page": page,
        "meters": [dict(m) for m in METERS],
        "components": [dict(c) for c in COMPONENTS],
    }
    entry.update(change)
    return entry


def read(**change: Any) -> dict[str, Any]:
    return {
        "meters": [dict(m) for m in METERS],
        "components": [dict(c) for c in COMPONENTS],
    } | change


def verdict(t: dict[str, Any], r: dict[str, Any]) -> tuple[bool, bool, bool]:
    from mkc.extraction.vision_check import compare

    v = compare(t, r)
    return v.meters, v.upstream, v.components


# --- the comparison rule (ruling 4) ------------------------------------------------------


def test_all_correct() -> None:
    assert verdict(truth(), read()) == (True, True, True)


def test_order_case_and_spaces_do_not_matter() -> None:
    shuffled = read(
        meters=[{"label": " z2", "upstream": "z1 "}, {"label": "Z1 ", "upstream": None}],
        components=[{"kind": "wr", "attached_to": "Z2"}, {"kind": " G", "attached_to": "z2"}],
    )
    assert verdict(truth(), shuffled) == (True, True, True)


def test_duplicates_collapse() -> None:
    twice = read(components=[*COMPONENTS, COMPONENTS[0]])
    assert verdict(truth(), twice) == (True, True, True)


def test_a_missing_meter_is_not_meters_correct() -> None:
    assert verdict(truth(), read(meters=[METERS[0]]))[0] is False


def test_an_extra_meter_is_not_meters_correct() -> None:
    extra = read(meters=[*METERS, {"label": "Z3", "upstream": "Z1"}])
    assert verdict(truth(), extra)[0] is False


def test_a_wrong_upstream_is_only_upstream_wrong() -> None:
    wrong = read(meters=[METERS[0], {"label": "Z2", "upstream": None}])
    assert verdict(truth(), wrong) == (True, False, True)


def test_an_extra_component_is_only_components_wrong() -> None:
    extra = read(components=[*COMPONENTS, {"kind": "B", "attached_to": "Z1"}])
    assert verdict(truth(), extra) == (True, True, False)


def test_a_component_on_the_wrong_meter_is_only_components_wrong() -> None:
    moved = read(components=[COMPONENTS[0], {"kind": "WR", "attached_to": "Z1"}])
    assert verdict(truth(), moved) == (True, True, False)


def test_extra_draft_fields_in_the_read_are_ignored() -> None:
    full = read(
        meters=[
            {"label": "Z1", "purpose": "Zweirichtung", "directions": ["Bezug"], "upstream": None},
            {
                "label": "Z2",
                "purpose": "Erzeugung",
                "directions": ["Einspeisung"],
                "upstream": "Z1",
            },
        ]
    )
    assert verdict(truth(), full) == (True, True, True)


# --- truth first (ruling 2) --------------------------------------------------------------


@pytest.mark.parametrize(
    "unfilled",
    [{"meters": None}, {"meters": []}, {"components": None}],
    ids=["meters-null", "meters-empty", "components-null"],
)
def test_an_unfilled_truth_entry_is_refused(unfilled: dict[str, Any]) -> None:
    from mkc.extraction.vision_check import compare

    with pytest.raises(ValueError):
        compare(truth(**unfilled), read())


def test_a_missing_truth_field_is_refused() -> None:
    from mkc.extraction.vision_check import compare

    entry = truth()
    del entry["components"]
    with pytest.raises(ValueError):
        compare(entry, read())


def test_no_components_is_a_filled_answer() -> None:
    """A single-meter concept has no components: `[]` is verified, `null` is unfilled."""
    single = truth(meters=[{"label": "Z1", "upstream": None}], components=[])
    assert verdict(single, read(meters=[{"label": "Z1", "upstream": None}], components=[])) == (
        True,
        True,
        True,
    )


def test_load_truth_reads_the_sheet(tmp_path: Path) -> None:
    from mkc.extraction.vision_check import load_truth

    sheet = tmp_path / "truth.yaml"
    sheet.write_text(
        "concepts:\n"
        "  - operator: stromnetz-berlin\n"
        '    concept: "3"\n'
        "    page: 4\n"
        "    meters:\n"
        "      - {label: Z1, upstream: null}\n"
        "      - {label: Z2, upstream: Z1}\n"
        "    components:\n"
        "      - {kind: G, attached_to: Z2}\n"
        "      - {kind: WR, attached_to: Z2}\n"
        "  - operator: stromnetz-berlin\n"
        '    concept: "4.4"\n'
        "    page: 5\n"
        "    meters: null\n"
        "    components: null\n",
        encoding="utf-8",
    )
    entries = load_truth(sheet)
    assert [e["concept"] for e in entries] == ["3", "4.4"]
    assert verdict(entries[0], read()) == (True, True, True)
    assert entries[1]["meters"] is None and entries[1]["components"] is None


# --- one vision call per concept (ruling 1) ----------------------------------------------


def berlin_pdf() -> bytes:
    """Cover, contents, then concepts 1, 3 and 4.4 on pages 3, 4 and 5."""
    return make_pdf(berlin_pages(["1", "3", "4.4"]))


def reply_text(**change: Any) -> str:
    meters = [
        {"label": "Z1", "purpose": "Zweirichtung", "directions": ["Bezug", "Einspeisung"],
         "upstream": None},
        {"label": "Z2", "purpose": "Erzeugung", "directions": ["Einspeisung"], "upstream": "Z1"},
    ]  # fmt: skip
    return json.dumps({"meters": meters, "components": COMPONENTS} | change)


def make_client(
    model: FakeChatModel | None,
    traces: list[CallTrace],
    mode: str = "live",
    store: ReplayStore | None = None,
) -> ModelClient:
    def factory(provider: Provider, name: str, timeout: float) -> FakeChatModel:
        if model is None:
            raise AssertionError("replay must not build a provider model")
        return model

    return ModelClient(
        config(),
        factory,
        mode=mode,  # type: ignore[arg-type]
        store=store,
        tracers=[traces.append],
    )


def images_sent(messages: list[BaseMessage]) -> list[bytes]:
    found: list[bytes] = []
    for message in messages:
        if isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, dict) and block.get("type") == "image":
                    found.append(base64.b64decode(block["base64"]))
    return found


def check(client: ModelClient, pdf: bytes, entries: list[dict[str, Any]]) -> list[Any]:
    from mkc.extraction.vision_check import check_concepts

    return list(check_concepts(client, pdf, entries, dpi=DPI))


def test_one_vision_call_with_the_rendered_region() -> None:
    from mkc.extraction.render import render_region
    from mkc.extraction.segment import segment_berlin

    pdf = berlin_pdf()
    model = FakeChatModel(responses=[ai(reply_text())])
    traces: list[CallTrace] = []
    rows = check(make_client(model, traces), pdf, [truth("3", 4)])
    assert [(r.role, r.method) for r in traces] == [("extract_vision", "vision")]
    assert len(model.seen) == 1
    (region,) = [r for r in segment_berlin(pdf) if r.number_hint == "3"]
    assert images_sent(model.seen[0]) == [render_region(pdf, 4, region.bbox, DPI).png]
    ((concept, v),) = rows
    assert concept == "3"
    assert (v.meters, v.upstream, v.components) == (True, True, True)


def test_one_call_per_concept_in_truth_order() -> None:
    model = FakeChatModel(responses=[ai(reply_text()), ai(reply_text(components=[COMPONENTS[0]]))])
    traces: list[CallTrace] = []
    rows = check(make_client(model, traces), berlin_pdf(), [truth("4.4", 5), truth("1", 3)])
    assert len(traces) == 2
    assert [c for c, _ in rows] == ["4.4", "1"]
    assert [v.components for _, v in rows] == [True, False]


def test_an_unfilled_sheet_makes_no_call() -> None:
    model = FakeChatModel(responses=[ai(reply_text())])
    traces: list[CallTrace] = []
    entries = [truth("3", 4), truth("4.4", 5, meters=None, components=None)]
    with pytest.raises(ValueError):
        check(make_client(model, traces), berlin_pdf(), entries)
    assert model.seen == [] and traces == [], "truth first: no vision call on an unfilled sheet"


def test_a_concept_not_in_the_document_makes_no_call() -> None:
    model = FakeChatModel(responses=[ai(reply_text())])
    traces: list[CallTrace] = []
    with pytest.raises(ValueError):
        check(make_client(model, traces), berlin_pdf(), [truth("3", 4), truth("9.9", 6)])
    assert model.seen == []


def test_a_page_that_disagrees_with_the_segmenter_makes_no_call() -> None:
    model = FakeChatModel(responses=[ai(reply_text())])
    traces: list[CallTrace] = []
    with pytest.raises(ValueError):
        check(make_client(model, traces), berlin_pdf(), [truth("3", 5)])
    assert model.seen == []


def test_a_fenced_json_reply_is_read() -> None:
    model = FakeChatModel(responses=[ai("```json\n" + reply_text() + "\n```")])
    ((_, v),) = check(make_client(model, []), berlin_pdf(), [truth("3", 4)])
    assert (v.meters, v.upstream, v.components) == (True, True, True)


@pytest.mark.parametrize(
    "text",
    ["I cannot read this diagram.", '{"meters": "Z1"}', "", '{"meters": [{"upstream": "Z1"}]}'],
    ids=["prose", "wrong-shape", "empty", "meter-without-label"],
)
def test_an_unreadable_reply_is_never_correct(text: str) -> None:
    model = FakeChatModel(responses=[ai(text)])
    try:
        rows = check(make_client(model, []), berlin_pdf(), [truth("3", 4)])
    except ValueError:
        return  # refusing the reply is fine too
    ((_, v),) = rows
    assert (v.meters, v.upstream, v.components) == (False, False, False)


def test_replay_gives_the_same_rows_without_a_provider(tmp_path: Path) -> None:
    pdf = berlin_pdf()
    store = ReplayStore(tmp_path / "replay")
    recorded = check(
        make_client(FakeChatModel(responses=[ai(reply_text())]), [], "record", store),
        pdf,
        [truth("3", 4)],
    )
    traces: list[CallTrace] = []
    replayed = check(make_client(None, traces, "replay", store), pdf, [truth("3", 4)])
    assert [(c, v.meters, v.upstream, v.components) for c, v in replayed] == [
        (c, v.meters, v.upstream, v.components) for c, v in recorded
    ]
    assert [t.mode for t in traces] == ["replay"]
    for file in (tmp_path / "replay").glob("*.json"):
        assert "base64" not in file.read_text(encoding="utf-8"), "recordings hold replies only"


# --- the result table and the CLI --------------------------------------------------------


def test_results_table_has_the_pinned_header_and_yes_no_cells() -> None:
    from mkc.extraction.vision_check import compare, results_table

    rows = [
        ("3", compare(truth(), read())),
        ("4.4", compare(truth(), read(meters=[METERS[0], {"label": "Z2", "upstream": None}]))),
    ]
    lines = [line for line in results_table(rows).splitlines() if line.strip()]
    cells = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    assert cells[0] == ["concept", "meters correct", "upstream correct", "components correct"]
    assert set("".join(cells[1])) <= set("-: ")
    assert cells[2:] == [["3", "yes", "yes", "yes"], ["4.4", "yes", "no", "yes"]]


def test_the_cli_has_help() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "mkc.extraction.vision_check", "--help"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert "truth" in done.stdout.lower()


# --- the sheet in the repo (ruling 2: facts and page references only) -------------------

SHEET = BACKEND / "data" / "go_no_go" / "truth.yaml"
ENTRY_KEYS = {"operator", "concept", "page", "meters", "components"}
METER_KEYS = {"label", "upstream"}
COMPONENT_KEYS = {"kind", "attached_to"}
MAX_FACT = 40
"""The longest string a fact may be: labels, kinds, concept numbers; no PDF text blocks."""


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def test_the_sheet_holds_five_berlin_concepts_as_facts_only() -> None:
    import yaml

    assert SHEET.is_file(), f"{SHEET} missing: the blank truth sheet comes first"
    assert SHEET.stat().st_size < 8_000, "facts and page references only, no images"
    data = yaml.safe_load(SHEET.read_text(encoding="utf-8"))
    assert set(data) == {"concepts"}
    entries = data["concepts"]
    assert len(entries) == 5
    assert len({e["concept"] for e in entries}) == 5
    for entry in entries:
        assert set(entry) == ENTRY_KEYS, entry
        assert entry["operator"] == "stromnetz-berlin"
        assert isinstance(entry["concept"], str) and entry["concept"], entry
        assert isinstance(entry["page"], int) and entry["page"] >= 1, entry
        for meter in entry["meters"] or []:
            assert set(meter) == METER_KEYS, meter
        for component in entry["components"] or []:
            assert set(component) == COMPONENT_KEYS, component
        assert all(len(s) <= MAX_FACT for s in strings(entry)), entry


def test_the_sheet_loads() -> None:
    from mkc.extraction.vision_check import load_truth

    assert len(load_truth(SHEET)) == 5
