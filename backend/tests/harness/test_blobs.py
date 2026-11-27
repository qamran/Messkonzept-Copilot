"""MKC-16.2: large tool results are stored as blob refs (decision 56)."""

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from mkc.harness.blobs import DbBlobStore
from mkc.harness.checkpoint import TurnRecord, save_turn, stored_result
from mkc.harness.limits import Limits
from mkc.harness.loop import run_item
from mkc.models.types import Message, ToolCall
from tests.harness.test_loop import READ, SAVE, Tools, client_for, start, turns
from tests.models.fakes import ai, fake

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def blob_rows(engine: Engine, ref: str) -> int:
    digest = ref.removeprefix("blob:sha256:")
    with engine.connect() as conn:
        query = text("select count(*) from blob where sha256 = :d")
        return int(conn.execute(query, {"d": digest}).scalar_one())


def test_put_is_content_addressed_and_idempotent(engine: Engine) -> None:
    data = "Zählerplatz mit zwei Messlokationen".encode()
    with Session(engine) as session:
        blobs = DbBlobStore(session)
        ref = blobs.put(data)
        assert blobs.put(data) == ref
        session.commit()
        assert ref == "blob:sha256:" + hashlib.sha256(data).hexdigest()
        assert blobs.get(ref) == data
    assert blob_rows(engine, ref) == 1


def test_get_of_an_unknown_ref_raises_key_error(engine: Engine) -> None:
    with Session(engine) as session, pytest.raises(KeyError):
        DbBlobStore(session).get("blob:sha256:" + "0" * 64)


def turn_with(item_id: int, data: str) -> TurnRecord:
    call = ToolCall(id="c1", name="extract_text", args={"page": 1})
    result = {"ok": True, "data": data, "error": None}
    return TurnRecord(
        item_id=item_id,
        number=1,
        assistant=Message(role="assistant", content="", tool_calls=[call]),
        results=[{"tool_call_id": "c1", "name": "extract_text", "result": result}],
        cost_eur=Decimal(0),
    )


def test_a_large_result_is_stored_as_a_ref(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    with Session(engine) as session:
        blobs = DbBlobStore(session)
        save_turn(session, turn_with(item_id, "x" * 500), blobs=blobs, inline_max_bytes=100)
        session.commit()
        (row,) = turns(engine, item_id)
        (entry,) = row.tool_results
        assert "result" not in entry
        assert entry["result_ref"]["ref"].startswith("blob:sha256:")
        assert entry["result_ref"]["bytes"] > 500
        assert stored_result(entry, blobs) == {"ok": True, "data": "x" * 500, "error": None}
    assert blob_rows(engine, entry["result_ref"]["ref"]) == 1


def test_a_small_result_stays_inline(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    with Session(engine) as session:
        blobs = DbBlobStore(session)
        save_turn(session, turn_with(item_id, "short"), blobs=blobs, inline_max_bytes=100)
        session.commit()
        (entry,) = turns(engine, item_id)[0].tool_results
        assert entry["result"]["data"] == "short" and "result_ref" not in entry
        assert stored_result(entry, blobs)["data"] == "short"


def test_the_loop_stores_large_tool_output_as_a_ref(engine: Engine) -> None:
    _, (item_id,) = start(engine)
    model = fake(ai(tool_calls=[READ]), ai(tool_calls=[SAVE]))
    with Session(engine) as session:
        run_item(item_id, session=session, client=client_for(model),
                 registry=Tools(text="Seite " * 400).registry(), limits=Limits(max_steps_item=3),
                 inline_max_bytes=1000)  # fmt: skip
    first, second = turns(engine, item_id)
    assert "result_ref" in first.tool_results[0]
    assert "result" in second.tool_results[0]  # the save's small result stays inline
    # the model still saw the full text in the same run
    assert "Seite Seite" in str(model.seen[1][-1].content)


def test_0005_creates_blob_and_downgrades(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))

    def columns() -> set[str]:
        engine = create_engine(database_env)
        try:
            with engine.connect() as conn:
                insp = inspect(conn)
                return (
                    {c["name"] for c in insp.get_columns("blob")}
                    if insp.has_table("blob")
                    else set()
                )
        finally:
            engine.dispose()

    command.upgrade(config, "head")
    assert columns() == {"sha256", "data", "size", "created_at"}
    command.downgrade(config, "0004")
    assert columns() == set()
    command.upgrade(config, "head")
    assert columns() == {"sha256", "data", "size", "created_at"}
