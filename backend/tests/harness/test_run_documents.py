"""MKC-23 (PR #215 finding 6): a real run gets the real document tools.

`execute_run` (and the worker, `tests/worker/test_executor_documents.py`) must pass a
`DocumentOps` to `default_registry`, or `extract_text`, `extract_tables` and
`render_region` answer `not_implemented` in production. Pinned (assumption):
`execute_run(..., documents=DocumentOps(...))` with the default registry.
"""

import hashlib
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Item, Run
from mkc.harness.limits import Limits
from mkc.harness.runner import execute_run
from tests.extraction.conftest import MemoryStore
from tests.extraction.drafts import valid_draft
from tests.extraction.synthetic import CONCEPT_BBOX, TITLE, concept_page_pdf
from tests.harness.test_loop import call, client_for, turns
from tests.models.fakes import FakeChatModel, ai


def item_for(engine: Engine, document_hash: str) -> tuple[int, int]:
    """A running run with one queued item for the document with this sha256."""
    with Session(engine) as session, session.begin():
        run = Run(state="running")
        session.add(run)
        session.flush()
        item = Item(run_id=run.id, concept_key="3.2", document_hash=document_hash,
                    task={"page": 1}, state="queued")  # fmt: skip
        session.add(item)
        session.flush()
        return run.id, item.id


def replies() -> list[Any]:
    # the region's bbox, as the item task gives it: without one the page's sidebar is read
    # too (decision 76), and its "Messkonzepte" lands inside the wrapped title
    read = call("extract_text", "r1", page=1, bbox=list(CONCEPT_BBOX))
    render = call("render_region", "g1", page=1, bbox=[72.0, 72.0, 144.0, 144.0], dpi=72)
    save = call("save_draft", "s1", draft=valid_draft())
    return [ai(tool_calls=[read, render]), ai(tool_calls=[save])]


def first_results(engine: Engine, item_id: int) -> dict[str, dict[str, Any]]:
    return {r["name"]: r["result"] for r in turns(engine, item_id)[0].tool_results}


def test_execute_run_passes_documents_to_the_registry(engine: Engine) -> None:
    from mkc.extraction.operations import DocumentOps

    pdf = concept_page_pdf()
    store = MemoryStore()
    store.put(pdf)
    run_id, item_id = item_for(engine, hashlib.sha256(pdf).hexdigest())
    with Session(engine) as session:
        execute_run(
            run_id,
            session=session,
            sessions=sessionmaker(bind=engine),
            client=client_for(FakeChatModel(responses=replies())),
            limits=Limits(max_steps_item=4),
            documents=DocumentOps(sessionmaker(bind=engine), store),
        )
    results = first_results(engine, item_id)
    assert results["extract_text"]["ok"], results["extract_text"]
    assert results["extract_text"]["data"]["title"] == TITLE
    assert results["render_region"]["ok"], results["render_region"]
