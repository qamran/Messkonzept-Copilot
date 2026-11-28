"""MKC-23 (PR #215 finding 6): the worker's runs get the real document tools.

The executor builds the default registry for each run (`registry=None`); its `extract_text`
must read the item's PDF from the configured store, not answer `not_implemented`. Pinned
(assumption): the executor's `DocumentOps` uses `storage_from_settings(settings)`, the store
it already uses for large turn results.
"""

import hashlib

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from tests.extraction.conftest import MemoryStore
from tests.extraction.synthetic import TITLE, concept_page_pdf
from tests.harness.test_run_documents import first_results, item_for, replies
from tests.models.fakes import FakeChatModel
from tests.worker.test_executor import client_for, settings


def test_the_executor_runs_with_the_real_document_tools(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.worker.executor import Executor

    pdf = concept_page_pdf()
    store = MemoryStore()
    store.put(pdf)
    monkeypatch.setattr("mkc.worker.executor.storage_from_settings", lambda s: store)
    run_id, item_id = item_for(engine, hashlib.sha256(pdf).hexdigest())
    model = FakeChatModel(responses=replies())
    worker = Executor(
        settings(),
        sessions=sessionmaker(bind=engine),
        client_factory=lambda: client_for(model),
        owner="w-documents",
    )
    with worker:
        assert worker.run_once(run_id) is True
    results = first_results(engine, item_id)
    assert results["extract_text"]["ok"], results["extract_text"]
    assert results["extract_text"]["data"]["title"] == TITLE
    assert results["render_region"]["ok"], results["render_region"]
