"""MKC-24: gold export and import for verification, and blind labelling (feature 33, design
11.1), lane A2. The UI for blind mode comes with MKC-29; this is the backend.

Pinned interface:

    mkc gold export --out FILE                       # every drafted item, JSON
    mkc gold export --out FILE --blind --key K ...   # blind items for these keys
    mkc gold import FILE --verified-by NAME          # --verified-by is required
    mkc.gold.exchange.export_items(session, *, blind: bool = False,
                                   keys: Sequence[str] | None = None) -> dict
        # the document the CLI writes; MKC-29's blind screen can reuse it

File: JSON `{"items": [...]}`. A drafted item has `kind`, `key`, `split`, `blind` (false),
`payload` and `drafted_by`. A blind item has `key` and `blind: true`, and no draft at all:
no payload content, no drafter (keys, operator, concept and page references only).

A blind label is a second item of the same key next to the drafted one, so blind labels can
be compared with verified drafts (design 11.1). A blind export creates (or keeps) that item
with `blind = true`; importing it with a filled-in `payload` sets `verified_by`, and
`drafted_by` stays empty. Import validates each payload as `MesskonzeptDraft`, is all or
nothing, and is idempotent by key.

Data rule (AGENTS.md): files hold facts and page references only. An export whose payload
holds an image (a data URI or a base64 run) or a long text block is refused.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner, Result

from mkc.cli import app
from tests.gold.conftest import SENTINEL, SENTINEL_LBS, draft_payload

runner = CliRunner()
GOLD_MODEL = "openrouter:anthropic/claude-haiku-5.5"
KEY = "stromnetz-berlin:4.1"
OTHER = "stromnetz-berlin:5"


def mkc(*args: str) -> Result:
    return runner.invoke(app, list(args))


def add_drafted(engine: Engine, key: str = KEY, **payload: Any) -> None:
    from mkc.db.models import GoldItem

    with Session(engine) as session, session.begin():
        session.add(
            GoldItem(kind="concept", key=key, split="dev", blind=False,
                     payload=draft_payload(**payload), drafted_by=GOLD_MODEL, verified_by=None)
        )  # fmt: skip


def rows(engine: Engine, key: str = KEY) -> dict[bool, Any]:
    """The items of `key`, by their `blind` flag."""
    from mkc.db.models import GoldItem

    with Session(engine) as session:
        found = list(session.scalars(select(GoldItem).where(GoldItem.key == key)))
        session.expunge_all()
    by_blind = {row.blind: row for row in found}
    assert len(by_blind) == len(found), "one drafted and at most one blind item per key"
    return by_blind


def read(path: Path) -> list[dict[str, Any]]:
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    assert isinstance(items, list)
    return items


def write(path: Path, items: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")


def test_gold_sub_app_has_the_four_commands() -> None:
    result = mkc("gold", "--help")
    assert result.exit_code == 0, result.output
    for command in ("split", "draft", "export", "import"):
        assert command in result.output, command


# --- blind mode ----------------------------------------------------------------------


def test_blind_mode_hides_draft_payload(gold_engine: Engine, tmp_path: Path) -> None:
    add_drafted(gold_engine)
    out = tmp_path / "blind.json"
    result = mkc("gold", "export", "--out", str(out), "--blind", "--key", KEY)
    assert result.exit_code == 0, result.output

    raw = out.read_bytes()
    assert SENTINEL.encode() not in raw, "a draft value is in the blind export"
    assert SENTINEL_LBS.encode() not in raw, "the draft's LBS code is in the blind export"
    assert b"claude-haiku" not in raw and b'drafted_by": "' not in raw
    [item] = read(out)
    assert item["key"] == KEY
    assert item["blind"] is True
    assert not item.get("payload")
    assert not item.get("drafted_by")

    by_blind = rows(gold_engine)
    assert by_blind[True].drafted_by is None
    assert not by_blind[True].payload
    assert by_blind[False].payload == draft_payload(), "the drafted item stays as it was"

    from mkc.gold.exchange import export_items

    with Session(gold_engine) as session, session.begin():
        document = export_items(session, blind=True, keys=[KEY])
    text = json.dumps(document)
    assert SENTINEL not in text and SENTINEL_LBS not in text and "claude-haiku" not in text
    assert [i["key"] for i in document["items"]] == [KEY]


def test_blind_label_import_sets_verified_by_and_keeps_drafted_by_empty(
    gold_engine: Engine, tmp_path: Path
) -> None:
    add_drafted(gold_engine)
    out = tmp_path / "blind.json"
    assert mkc("gold", "export", "--out", str(out), "--blind", "--key", KEY).exit_code == 0
    items = read(out)
    label = draft_payload(title="Label from scratch")
    items[0]["payload"] = label
    write(out, items)

    for _ in range(2):  # idempotent by key
        result = mkc("gold", "import", str(out), "--verified-by", "qamran")
        assert result.exit_code == 0, result.output
        by_blind = rows(gold_engine)
        assert by_blind[True].payload == label
        assert by_blind[True].verified_by == "qamran"
        assert by_blind[True].drafted_by is None
        assert by_blind[False].payload == draft_payload()
        assert by_blind[False].verified_by is None


def test_an_unfilled_blind_item_is_not_verified(gold_engine: Engine, tmp_path: Path) -> None:
    add_drafted(gold_engine)
    out = tmp_path / "blind.json"
    assert mkc("gold", "export", "--out", str(out), "--blind", "--key", KEY).exit_code == 0
    mkc("gold", "import", str(out), "--verified-by", "qamran")
    assert rows(gold_engine)[True].verified_by is None


# --- export, edit, import ------------------------------------------------------------


def test_export_edit_import_round_trip(gold_engine: Engine, tmp_path: Path) -> None:
    add_drafted(gold_engine)
    add_drafted(gold_engine, key=OTHER, number="5")
    out = tmp_path / "gold.json"
    result = mkc("gold", "export", "--out", str(out))
    assert result.exit_code == 0, result.output
    items = {i["key"]: i for i in read(out)}
    assert set(items) == {KEY, OTHER}
    assert items[KEY]["payload"] == draft_payload()
    assert items[KEY]["drafted_by"] == GOLD_MODEL
    assert (items[KEY]["kind"], items[KEY]["split"], items[KEY]["blind"]) == (
        "concept", "dev", False,
    )  # fmt: skip

    items[KEY]["payload"]["title"] = "Corrected by the user"
    write(out, list(items.values()))
    for _ in range(2):  # a re-import by key changes nothing
        result = mkc("gold", "import", str(out), "--verified-by", "qamran")
        assert result.exit_code == 0, result.output
        row = rows(gold_engine)[False]
        assert row.payload["title"] == "Corrected by the user"
        assert row.verified_by == "qamran"
        assert row.drafted_by == GOLD_MODEL
        assert len(rows(gold_engine, OTHER)) == 1
        assert list(rows(gold_engine)) == [False]


def test_import_needs_verified_by(gold_engine: Engine, tmp_path: Path) -> None:
    add_drafted(gold_engine)
    out = tmp_path / "gold.json"
    assert mkc("gold", "export", "--out", str(out)).exit_code == 0
    assert mkc("gold", "import", str(out)).exit_code != 0
    assert rows(gold_engine)[False].verified_by is None


def test_an_invalid_payload_is_refused_and_nothing_is_imported(
    gold_engine: Engine, tmp_path: Path
) -> None:
    add_drafted(gold_engine)
    add_drafted(gold_engine, key=OTHER, number="5")
    out = tmp_path / "gold.json"
    assert mkc("gold", "export", "--out", str(out)).exit_code == 0
    items = {i["key"]: i for i in read(out)}
    items[KEY]["payload"]["title"] = "A valid correction"
    del items[OTHER]["payload"]["meters"]  # not a MesskonzeptDraft any more
    write(out, list(items.values()))

    result = mkc("gold", "import", str(out), "--verified-by", "qamran")
    assert result.exit_code == 2, result.output
    assert OTHER in result.output
    assert rows(gold_engine)[False].verified_by is None, "all or nothing"
    assert rows(gold_engine)[False].payload == draft_payload()


# --- data rule: facts and page references only ----------------------------------------

IMAGE_URI = "data:image/png;base64," + "iVBORw0KGgoAAAANSUhEUgAA" * 40
BASE64_RUN = "QUJD" * 300
TEXT_BLOCK = ("Der Messstellenbetreiber stellt die Messeinrichtung bereit. " * 90).strip()


@pytest.mark.parametrize(
    "payload",
    [
        {"footnotes": [IMAGE_URI]},
        {"footnotes": [BASE64_RUN]},
        {"footnotes": [TEXT_BLOCK]},
        {"title": TEXT_BLOCK},
    ],
    ids=["data-uri-image", "base64-run", "text-block-footnote", "text-block-title"],
)
def test_export_refuses_images_and_text_blocks(
    gold_engine: Engine, tmp_path: Path, payload: dict[str, Any]
) -> None:
    assert len(TEXT_BLOCK) > 5_000
    add_drafted(gold_engine, **payload)
    out = tmp_path / "gold.json"
    result = mkc("gold", "export", "--out", str(out))
    assert result.exit_code != 0, result.output
    assert KEY in result.output
    written = out.read_text(encoding="utf-8") if out.exists() else ""
    assert IMAGE_URI not in written and BASE64_RUN not in written and TEXT_BLOCK not in written


def test_a_normal_footnote_exports(gold_engine: Engine, tmp_path: Path) -> None:
    footnote = (
        "Bei Anlagen mit einer installierten Leistung bis 100 kW ist ein "
        "Zweirichtungszaehler einzusetzen; die Erzeugung wird nicht gesondert gemessen. "
        "Die Zuordnung der Lokationsbuendelstruktur erfolgt nach der Codeliste des BDEW, "
        "Ausgabe 2026, Tabelle 3, und gilt nur fuer den Netzanschluss in Niederspannung."
    )
    assert 250 < len(footnote) < 400
    add_drafted(gold_engine, footnotes=[footnote])
    out = tmp_path / "gold.json"
    result = mkc("gold", "export", "--out", str(out))
    assert result.exit_code == 0, result.output
    assert read(out)[0]["payload"]["footnotes"] == [footnote]
