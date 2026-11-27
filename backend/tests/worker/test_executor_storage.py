"""MKC-21.4 (mutation pass, survivors 18 to 20): large turn results reach the configured
store through `process_run` and through the executor, also on the turn that ends an item,
and never the `blob` table.
"""

from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Blob
from mkc.harness.blobs import PREFIX
from mkc.harness.limits import Limits
from mkc.harness.loop import process_run
from tests.extraction.conftest import MemoryStore
from tests.harness.conftest import make_run
from tests.harness.test_loop import SAVE, Tools, call, client_for, turns
from tests.models.fakes import FakeChatModel, ai
from tests.worker.test_executor import settings


def _replies() -> list[Any]:
    """Turn 1 reads a page; turn 2 reads one more and saves, which ends the item."""
    read = call("extract_text", "r1", page=1)
    return [ai(tool_calls=[read]), ai(tool_calls=[call("extract_text", "r2", page=2), SAVE])]


def _refs(engine: Engine, item_id: int) -> list[str]:
    stored = [entry for t in turns(engine, item_id) for entry in t.tool_results]
    return [e["result_ref"]["ref"] for e in stored if "result_ref" in e]


def _in_blob_table(engine: Engine, ref: str) -> bool:
    with Session(engine) as session:
        digest = ref.removeprefix(PREFIX)
        return session.scalar(select(func.count()).where(Blob.sha256 == digest)) == 1


def _assert_in_store_only(engine: Engine, item_id: int, store: MemoryStore) -> None:
    refs = _refs(engine, item_id)
    assert len(refs) == 2, "both turns, also the one that ends the item, store a ref"
    for ref in refs:
        assert ref in store.data
        assert not _in_blob_table(engine, ref)


def test_process_run_sends_every_large_result_to_the_store(engine: Engine) -> None:
    run_id, (item_id,) = make_run(engine, "queued")
    store = MemoryStore()
    tools = Tools(text="Prozess-Seite " * 400)  # a text no other test stores
    with Session(engine) as session:
        process_run(
            run_id, session=session, client=client_for(FakeChatModel(responses=_replies())),
            registry=tools.registry(), limits=Limits(max_steps_item=6),
            inline_max_bytes=1000, blobs=store,
        )  # fmt: skip
    _assert_in_store_only(engine, item_id, store)


def test_the_executor_sends_large_results_to_its_store(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.worker.executor import Executor

    store = MemoryStore()
    monkeypatch.setattr("mkc.worker.executor.storage_from_settings", lambda s: store)
    run_id, (item_id,) = make_run(engine, "queued")
    model = FakeChatModel(responses=_replies())
    worker = Executor(
        settings(turn_inline_max_bytes=1000),
        sessions=sessionmaker(bind=engine),
        client_factory=lambda: client_for(model),
        registry=Tools(text="Executor-Seite " * 400).registry(),
        owner="w-storage",
    )
    with worker:
        assert worker.run_once(run_id) is True
    _assert_in_store_only(engine, item_id, store)
