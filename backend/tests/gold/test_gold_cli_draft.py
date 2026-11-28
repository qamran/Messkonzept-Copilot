"""MKC-24.2 and 24.3, the development agent's own tests: `mkc gold draft` on a synthetic
Berlin-style PDF with a fake model, and the export/import edge cases decision 89 fixes."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from mkc.cli import app
from mkc.models.client import ModelClient
from tests.extraction.conftest import make_pdf
from tests.gold.conftest import draft_payload
from tests.gold.test_gold_draft import Recorder

runner = CliRunner()
PDF = make_pdf(
    [["Cover"], ["4.1 Ueberschusseinspeisung", "Z1 Zweirichtung"], ["5 Volleinspeisung"]]
)
SPLIT = """pinned_dev:
- stromnetz-berlin:5
dev:
- stromnetz-berlin:5
test:
- stromnetz-berlin:4.1
"""


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Recorder, Path]:
    recorder = Recorder(draft_payload())
    split = tmp_path / "split.yaml"
    split.write_text(SPLIT, encoding="utf-8")

    def client(settings: Any) -> ModelClient:
        from mkc.gold.cli import models_config

        return recorder.client(models_config(settings))

    monkeypatch.setattr("mkc.gold.cli.make_client", client)
    monkeypatch.setattr("mkc.gold.cli.fetch_catalogue", lambda operator: PDF)
    return recorder, split


def _rows(engine: Engine) -> list[Any]:
    from mkc.db.models import GoldItem

    with Session(engine) as session:
        rows = list(session.scalars(select(GoldItem).order_by(GoldItem.key, GoldItem.blind)))
        session.expunge_all()
    return rows


def test_draft_stores_the_key_with_its_side_and_the_real_source(
    gold_engine: Engine, fake: tuple[Recorder, Path]
) -> None:
    recorder, split = fake
    result = runner.invoke(app, ["gold", "draft", "--operator", "stromnetz-berlin",
                                 "--side", "test", "--split-file", str(split)])  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "stromnetz-berlin:4.1: openrouter:anthropic/claude-haiku-5.5" in result.output
    assert "EUR" in result.output
    [row] = _rows(gold_engine)
    assert (row.key, row.split, row.blind, row.verified_by) == (
        "stromnetz-berlin:4.1", "test", False, None,
    )  # fmt: skip
    assert row.payload["source"]["page"] == 2  # from the segmenter, not the model
    assert row.payload["source"]["document"] != "sha256:berlin-2026-09"
    [sent] = recorder.model.seen
    human = next(m for m in sent if m.type == "human")
    assert any(isinstance(b, dict) and b.get("type") == "image" for b in human.content)
    assert "Ueberschusseinspeisung" in str(human.content)


def test_draft_skips_pinned_keys_unless_asked(
    gold_engine: Engine, fake: tuple[Recorder, Path]
) -> None:
    recorder, split = fake
    args = ["gold", "draft", "--operator", "stromnetz-berlin", "--side", "dev",
            "--split-file", str(split)]  # fmt: skip
    result = runner.invoke(app, args)
    assert result.exit_code == 2 and "no key to draft" in result.output
    assert recorder.model.seen == []
    result = runner.invoke(app, [*args, "--include-pinned", "--no-image"])
    assert result.exit_code == 0, result.output
    assert [r.key for r in _rows(gold_engine)] == ["stromnetz-berlin:5"]


def test_draft_refuses_a_key_not_in_the_split(
    gold_engine: Engine, fake: tuple[Recorder, Path]
) -> None:
    recorder, split = fake
    result = runner.invoke(app, ["gold", "draft", "--operator", "stromnetz-berlin",
                                 "--key", "9", "--split-file", str(split)])  # fmt: skip
    assert result.exit_code == 2
    assert "stromnetz-berlin:9" in result.output
    assert recorder.model.seen == []


def test_blind_export_without_a_draft_takes_the_split_file(
    gold_engine: Engine, tmp_path: Path
) -> None:
    from mkc.gold.exchange import GoldFileError, export_items

    split = tmp_path / "split.yaml"
    split.write_text(SPLIT, encoding="utf-8")
    with Session(gold_engine) as session, session.begin():
        doc = export_items(session, blind=True, keys=["stromnetz-berlin:5"], split_file=split)
    assert doc["items"] == [{"kind": "concept", "key": "stromnetz-berlin:5", "split": "dev",
                             "blind": True, "payload": None}]  # fmt: skip
    with (
        pytest.raises(GoldFileError, match="stromnetz-berlin:77"),
        Session(gold_engine) as session,
        session.begin(),
    ):
        export_items(session, blind=True, keys=["stromnetz-berlin:77"], split_file=split)


def test_an_unfilled_blind_import_keeps_an_earlier_label(
    gold_engine: Engine, tmp_path: Path
) -> None:
    from mkc.db.models import GoldItem

    label = draft_payload(title="My label")
    with Session(gold_engine) as session, session.begin():
        session.add(GoldItem(kind="concept", key="stromnetz-berlin:5", split="dev", blind=True,
                             payload=label, verified_by="qamran"))  # fmt: skip
    file = tmp_path / "blind.json"
    file.write_text(json.dumps({"items": [{"key": "stromnetz-berlin:5", "blind": True,
                                           "payload": None}]}), encoding="utf-8")  # fmt: skip
    result = runner.invoke(app, ["gold", "import", str(file), "--verified-by", "someone"])
    assert result.exit_code == 0, result.output
    [row] = _rows(gold_engine)
    assert (row.payload, row.verified_by) == (label, "qamran")


def test_import_of_a_key_without_an_item_imports_nothing(
    gold_engine: Engine, tmp_path: Path
) -> None:
    file = tmp_path / "gold.json"
    item = {"key": "stromnetz-berlin:5", "blind": False, "payload": draft_payload()}
    file.write_text(json.dumps({"items": [item]}), encoding="utf-8")
    result = runner.invoke(app, ["gold", "import", str(file), "--verified-by", "qamran"])
    assert result.exit_code == 2
    assert "stromnetz-berlin:5" in result.output
    assert _rows(gold_engine) == []


def test_a_verified_draft_is_not_redrafted(
    gold_engine: Engine, fake: tuple[Recorder, Path]
) -> None:
    from mkc.db.models import GoldItem

    recorder, split = fake
    with Session(gold_engine) as session, session.begin():
        session.add(GoldItem(kind="concept", key="stromnetz-berlin:4.1", split="test",
                             blind=False, payload=draft_payload(title="checked"),
                             drafted_by="openrouter:y/gold", verified_by="qamran"))  # fmt: skip
    result = runner.invoke(app, ["gold", "draft", "--operator", "stromnetz-berlin",
                                 "--key", "4.1", "--split-file", str(split)])  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "stromnetz-berlin:4.1: verified by qamran, skipped" in result.output
    assert recorder.model.seen == [], "no paid call for a verified item"
    [row] = _rows(gold_engine)
    assert row.payload["title"] == "checked"


def test_draft_stops_at_max_eur(gold_engine: Engine, fake: tuple[Recorder, Path]) -> None:
    recorder, split = fake
    args = [
        "gold",
        "draft",
        "--operator",
        "stromnetz-berlin",
        "--key",
        "4.1",
        "--key",
        "5",
        "--include-pinned",
        "--no-image",
        "--split-file",
        str(split),
        "--max-eur",
        "0.0001",
    ]
    result = runner.invoke(app, args)  # fmt: skip
    assert result.exit_code == 1, result.output
    assert "--max-eur" in result.output
    assert len(recorder.model.seen) == 1  # the first call costs about 0.00027 EUR (models.yaml)


def test_a_failed_call_is_reported_and_the_batch_goes_on(
    gold_engine: Engine, fake: tuple[Recorder, Path]
) -> None:
    from tests.gold.test_gold_draft import reply

    recorder, split = fake
    bad = draft_payload()
    del bad["meters"]
    recorder.model.responses = [reply(bad), reply(draft_payload())]
    args = [
        "gold",
        "draft",
        "--operator",
        "stromnetz-berlin",
        "--key",
        "4.1",
        "--key",
        "5",
        "--include-pinned",
        "--no-image",
        "--split-file",
        str(split),
    ]
    result = runner.invoke(app, args)  # fmt: skip
    assert result.exit_code == 1, result.output
    assert "stromnetz-berlin:4.1: failed" in result.output
    assert "cost unknown" in result.output
    assert "total:" in result.output
    assert [r.key for r in _rows(gold_engine)] == ["stromnetz-berlin:5"]


def test_store_refuses_a_payload_that_is_not_facts_only(gold_engine: Engine) -> None:
    from mkc.gold.draft import GoldDraft
    from mkc.gold.facts import FactsOnlyError
    from mkc.gold.store import store_gold_draft

    draft = GoldDraft(key="stromnetz-berlin:5", payload=draft_payload(footnotes=["x" * 2_001]),
                      drafted_by="openrouter:y/gold", cost_eur=0.0)  # fmt: skip
    with (
        pytest.raises(FactsOnlyError, match="stromnetz-berlin:5"),
        Session(gold_engine) as session,
        session.begin(),
    ):
        store_gold_draft(session, draft, split="dev")
    assert _rows(gold_engine) == []


def test_import_refuses_a_payload_that_is_not_facts_only(
    gold_engine: Engine, tmp_path: Path
) -> None:
    from mkc.db.models import GoldItem

    with Session(gold_engine) as session, session.begin():
        session.add(GoldItem(kind="concept", key="stromnetz-berlin:5", split="dev", blind=False,
                             payload=draft_payload(), drafted_by="openrouter:y/gold"))  # fmt: skip
    item = {"key": "stromnetz-berlin:5", "blind": False,
            "payload": draft_payload(footnotes=["data:image/png;base64,AAAA"])}  # fmt: skip
    file = tmp_path / "gold.json"
    file.write_text(json.dumps({"items": [item]}), encoding="utf-8")
    result = runner.invoke(app, ["gold", "import", str(file), "--verified-by", "qamran"])
    assert result.exit_code == 2
    assert "stromnetz-berlin:5" in result.output and "image" in result.output
    [row] = _rows(gold_engine)
    assert row.verified_by is None
