"""MKC-21.4 live test: the Berlin PDF goes into the real `mkc-storage` bucket and back.

Deselected by default. Run with the coordinator's go, with only the five `MKC_STORAGE_*`
variables from `backend/.env` exported (not `--env-file .env`: its `DATABASE_URL` is Supabase,
and the test database must stay local), as the runbook shows:
`uv run pytest -m live tests/extraction/test_live_storage.py`.
"""

import hashlib

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.harness.blobs import PREFIX


@pytest.mark.live
def test_berlin_pdf_round_trips_through_supabase_storage(
    engine: Engine, sessions: sessionmaker[Session]
) -> None:
    from mkc.extraction.fetch import fetch_document, http_get
    from mkc.extraction.segment import segment_document
    from mkc.harness.storage import storage_from_settings

    store = storage_from_settings(Settings())
    assert store is not None, "set the five MKC_STORAGE_* variables"
    doc = fetch_document("stromnetz-berlin", sessions=sessions, store=store, get=http_get)
    data = store.get(PREFIX + doc.sha256)
    assert hashlib.sha256(data).hexdigest() == doc.sha256
    assert len(segment_document(doc, store=store)) == 26
    with pytest.raises(KeyError):
        store.get(PREFIX + "0" * 64)
