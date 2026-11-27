"""MKC-21.4 (decision 56): large turn results go to the configured blob store (Supabase
Storage in production), and refs stored in the `blob` table before MKC-21 stay readable.
"""

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from mkc.db.models import Blob
from mkc.harness.blobs import PREFIX
from tests.extraction.conftest import MemoryStore
from tests.harness.test_loop import SAVE, Tools, turns
from tests.harness.test_resume import crash_after, go
from tests.models.fakes import ai, fake


def _in_blob_table(engine: Engine, ref: str) -> bool:
    digest = ref.removeprefix(PREFIX)
    with Session(engine) as session:
        return session.scalar(select(func.count()).where(Blob.sha256 == digest)) == 1


def _ref(engine: Engine, item_id: int) -> str:
    ref: str = turns(engine, item_id)[0].tool_results[0]["result_ref"]["ref"]
    return ref


def test_a_large_result_goes_to_the_store_and_resumes_from_it(engine: Engine) -> None:
    store = MemoryStore()
    big = Tools(text="Storage-Seite " * 400)  # a text no other test stores
    item_id = crash_after(engine, 1, big, inline_max_bytes=1000, blobs=store)
    ref = _ref(engine, item_id)
    assert ref in store.data
    assert not _in_blob_table(engine, ref), "nothing goes to the blob table when a store is set"
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools(), blobs=store)
    assert "Storage-Seite Storage-Seite" in str(model.seen[0][-1].content)


def test_a_ref_from_the_blob_table_resumes_with_a_store_set(engine: Engine) -> None:
    big = Tools(text="Tabellen-Seite " * 400)
    item_id = crash_after(engine, 1, big, inline_max_bytes=1000)
    assert _in_blob_table(engine, _ref(engine, item_id))
    model = fake(ai(tool_calls=[SAVE]))
    go(engine, item_id, model, Tools(), blobs=MemoryStore())
    assert "Tabellen-Seite Tabellen-Seite" in str(model.seen[0][-1].content)


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
