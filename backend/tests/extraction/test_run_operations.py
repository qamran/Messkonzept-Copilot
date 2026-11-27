"""MKC-21.5 (development agent): `fetch_document` and `segment_document` as run-level
operations, and `mkc run start --operator` (one queued item per concept region).

`DocumentOps(sessions, store, get=..., operators=...)` holds what the two operations need;
`default_registry(documents=...)` makes them real. Without it they stay placeholders, like
`save_draft` without `sessions`.
"""

import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mkc.harness.tools import ToolEnv
from mkc.models.types import ToolCall
from tests.extraction.conftest import (
    OPERATOR_ID,
    URL_OK,
    FakeGet,
    MemoryStore,
    berlin_pages,
    make_pdf,
    operators,
    rows,
)

RUN_ENV = ToolEnv(run_id=1)
ITEM_ENV = ToolEnv(run_id=1, item_id=2, document_hash="h", concept_key="1")


def _registry(sessions: sessionmaker[Session], store: MemoryStore, *pdfs: bytes) -> Any:
    from mkc.extraction.operations import DocumentOps
    from mkc.harness.registry import default_registry

    get = FakeGet([(URL_OK, pdf) for pdf in pdfs])
    docs = DocumentOps(sessions, store, get=get, operators=operators())
    return default_registry(documents=docs)


def _call(name: str, **args: Any) -> ToolCall:
    return ToolCall(id="c", name=name, args=args)


def test_fetch_and_segment_run_in_the_run_context(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry = _registry(sessions, store, make_pdf(berlin_pages(["1", "2a", "3"])))
    fetched = registry.execute(_call("fetch_document", operator_id=OPERATOR_ID), "run", RUN_ENV)
    assert fetched.ok, fetched.error
    assert fetched.data["edition"] == 1 and fetched.data["page_count"] == 6
    sha = fetched.data["sha256"]
    regions = registry.execute(_call("segment_document", document_hash=sha), "run", RUN_ENV)
    assert regions.ok, regions.error
    assert [r["number_hint"] for r in regions.data["regions"]] == ["1", "2a", "3"]
    assert [r["page"] for r in regions.data["regions"]] == [3, 4, 5]
    assert len(regions.data["regions"][0]["bbox"]) == 4


def test_both_stay_refused_in_the_item_context(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry = _registry(sessions, store, make_pdf(berlin_pages(["1"])))
    for call in (
        _call("fetch_document", operator_id=OPERATOR_ID),
        _call("segment_document", document_hash="0" * 64),
    ):
        result = registry.execute(call, "item", ITEM_ENV)
        assert result.error is not None and result.error.code == "tool_not_allowed"
    assert store.data == {}


def test_segment_of_an_unknown_hash_fails_as_a_tool_error(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry = _registry(sessions, store)
    result = registry.execute(_call("segment_document", document_hash="0" * 64), "run", RUN_ENV)
    assert result.error is not None and result.error.code == "tool_failed"


def test_a_refused_fetch_is_a_tool_error_and_writes_nothing(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry = _registry(sessions, store, b"<html>not a pdf</html>")
    result = registry.execute(_call("fetch_document", operator_id=OPERATOR_ID), "run", RUN_ENV)
    assert result.error is not None and "NotAPdf" in result.error.message
    assert rows(engine, "select id from source_document") == []


def test_document_by_hash_takes_the_newest_edition_with_that_hash(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import document_by_hash, fetch_document

    a, b = make_pdf(berlin_pages(["1"])), make_pdf(berlin_pages(["1", "2"]))
    get = FakeGet([(URL_OK, a), (URL_OK, b), (URL_OK, a)])
    kw = {"sessions": sessions, "store": store, "get": get, "operators": operators()}
    first, _, third = (fetch_document(OPERATOR_ID, **kw) for _ in range(3))
    with sessions() as session:
        found = document_by_hash(session, first.sha256)
        assert document_by_hash(session, "0" * 64) is None
    assert found is not None and found.edition == third.edition == 3


@pytest.fixture
def cli_docs(
    sessions: sessionmaker[Session], store: MemoryStore, monkeypatch: pytest.MonkeyPatch
) -> MemoryStore:
    """`mkc run start --operator` with the fake getter and the test operator."""
    from mkc.extraction.operations import DocumentOps

    get = FakeGet([(URL_OK, make_pdf(berlin_pages(["1", "2a", "3"])))])
    monkeypatch.setattr(
        "mkc.cli.make_documents",
        lambda settings, s: DocumentOps(s, store, get=get, operators=operators()),
    )
    return store


def test_run_start_from_an_operator_queues_one_item_per_concept(
    engine: Engine, cli_docs: MemoryStore
) -> None:
    from mkc.cli import app

    result = CliRunner().invoke(app, ["run", "start", "--operator", OPERATOR_ID])
    assert result.exit_code == 0, result.output
    match = re.search(r"run (\d+) created \(mode full\): 3 items", result.output)
    assert match, result.output
    assert "edition 1" in result.output
    run_id = int(match.group(1))
    items = rows(
        engine,
        f"select concept_key, document_hash, state, task from item where run_id = {run_id}"
        " order by id",
    )
    sha = rows(engine, "select sha256 from source_document")[0][0]
    assert [(i[0], i[1], i[2]) for i in items] == [
        ("1", sha, "queued"), ("2a", sha, "queued"), ("3", sha, "queued"),
    ]  # fmt: skip
    task = items[0][3]
    assert task["operator_id"] == OPERATOR_ID and task["page"] == 3 and task["edition"] == 1
    assert len(task["bbox"]) == 4


def test_run_start_needs_exactly_one_source(engine: Engine, cli_docs: MemoryStore) -> None:
    from mkc.cli import app

    assert CliRunner().invoke(app, ["run", "start"]).exit_code == 2
    both = ["run", "start", "--operator", OPERATOR_ID, "--items", "x.yaml"]
    assert CliRunner().invoke(app, both).exit_code == 2


def test_a_failed_fetch_creates_no_run(
    engine: Engine, sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.cli import app
    from mkc.extraction.operations import DocumentOps

    runs_before = rows(engine, "select count(*) from run")
    get = FakeGet([("https://evil.example/x.pdf", make_pdf(berlin_pages(["1"])))])
    monkeypatch.setattr(
        "mkc.cli.make_documents",
        lambda settings, s: DocumentOps(s, MemoryStore(), get=get, operators=operators()),
    )
    result = CliRunner().invoke(app, ["run", "start", "--operator", OPERATOR_ID])
    assert result.exit_code == 1
    assert "fetch_document" in result.output
    assert rows(engine, "select count(*) from run") == runs_before


def test_a_new_edition_keeps_its_number_and_flag_across_the_registry(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    v1, v2 = make_pdf(berlin_pages(["1"])), make_pdf(berlin_pages(["1", "2"]))
    registry = _registry(sessions, store, v1, v2)
    fetch = _call("fetch_document", operator_id=OPERATOR_ID)
    first = registry.execute(fetch, "run", RUN_ENV).data
    second = registry.execute(fetch, "run", RUN_ENV).data
    assert (first["edition"], first["new_edition"]) == (1, False)
    assert (second["edition"], second["new_edition"]) == (2, True)
    found = registry.execute(
        _call("segment_document", document_hash=second["sha256"]), "run", RUN_ENV
    ).data
    assert (found["operator_id"], found["edition"]) == (OPERATOR_ID, 2)


def test_run_start_reports_a_new_edition(
    engine: Engine, sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.cli import app
    from mkc.extraction.operations import DocumentOps

    store = MemoryStore()
    v1, v2 = make_pdf(berlin_pages(["1"])), make_pdf(berlin_pages(["1", "2"]))
    get = FakeGet([(URL_OK, v1), (URL_OK, v2)])
    monkeypatch.setattr(
        "mkc.cli.make_documents",
        lambda settings, s: DocumentOps(s, store, get=get, operators=operators()),
    )
    first = CliRunner().invoke(app, ["run", "start", "--operator", OPERATOR_ID])
    second = CliRunner().invoke(app, ["run", "start", "--operator", OPERATOR_ID])
    assert f"{OPERATOR_ID}: edition 1, sha256" in first.output
    assert f"{OPERATOR_ID}: edition 2, a new edition, sha256" in second.output
    run_id = int(re.findall(r"run (\d+) created", second.output)[0])
    tasks = rows(engine, f"select task from item where run_id = {run_id}")
    assert {t[0]["edition"] for t in tasks} == {2}


def test_operator_and_items_together_are_refused_before_anything_runs(
    engine: Engine, cli_docs: MemoryStore, tmp_path: Path
) -> None:
    from mkc.cli import app

    items = tmp_path / "items.yaml"
    items.write_text(
        "- {concept_key: MK-1, document_hash: h, task: {region: page 3}}\n", encoding="utf-8"
    )
    runs_before = rows(engine, "select count(*) from run")
    both = ["run", "start", "--operator", OPERATOR_ID, "--items", str(items)]
    result = CliRunner().invoke(app, both)
    assert result.exit_code == 2
    assert "exactly one of --operator and --items" in result.output
    assert cli_docs.data == {}, "nothing was fetched"
    assert rows(engine, "select count(*) from run") == runs_before
