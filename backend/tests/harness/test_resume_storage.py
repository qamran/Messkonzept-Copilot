"""MKC-21.4 (decision 56): large turn results go to the configured blob store (Supabase
Storage in production), and refs stored in the `blob` table before MKC-21 stay readable.
"""

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from mkc.db.models import Blob
from tests.extraction.conftest import MemoryStore
from tests.harness.test_loop import SAVE, Tools, turns
from tests.harness.test_resume import crash_after, go
from tests.models.fakes import ai, fake


def _blob_rows(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Blob)) or 0


def test_a_large_result_goes_to_the_store_and_resumes_from_it(engine: Engine) -> None:
    store = MemoryStore()
    big = Tools(text="Seite " * 400)
    item_id = crash_after(engine, 1, big, inline_max_bytes=1000, blobs=store)
    ref = turns(engine, item_id)[0].tool_results[0]["result_ref"]
    assert ref in store.data
    assert _blob_rows(engine) == 0, "nothing goes to the blob table when a store is set"
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools(), blobs=store)
    assert "Seite Seite" in str(model.seen[0][-1].content)


def test_a_ref_from_the_blob_table_resumes_with_a_store_set(engine: Engine) -> None:
    item_id = crash_after(engine, 1, Tools(text="Seite " * 400), inline_max_bytes=1000)
    assert _blob_rows(engine) == 1
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools(), blobs=MemoryStore())
    assert "Seite Seite" in str(model.seen[0][-1].content)


def test_the_executor_uses_storage_when_the_settings_name_it() -> None:
    from mkc.config import Settings
    from mkc.harness.storage import StorageBlobStore
    from mkc.worker.executor import Executor

    storage = {
        "storage_s3_endpoint": "https://p.storage.supabase.co/storage/v1/s3",
        "storage_s3_region": "eu-west-1",
        "storage_bucket": "mkc-storage",
        "storage_access_key_id": "id",
        "storage_secret_access_key": "secret",
    }
    kw = {"sessions": None, "client_factory": lambda: None}
    assert isinstance(Executor(Settings(**storage), **kw).blobs, StorageBlobStore)
    assert Executor(Settings(), **kw).blobs is None
