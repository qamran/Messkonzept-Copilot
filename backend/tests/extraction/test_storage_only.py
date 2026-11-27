"""MKC-21 success criterion: PDFs cached only in Storage and gitignored locally.

- `fetch_document` writes the PDF only through the injected `BlobStore` (Supabase Storage in
  production, a fake here): no file on disk, nothing in the Postgres `blob` table.
- `mkc.extraction.storage.LOCAL_CACHE_DIR` is where a local run may cache PDFs; every file
  in it is gitignored (checked with `git check-ignore`, also for names without `.pdf`).
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

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

REPO = Path(__file__).resolve().parents[3]


def test_fetch_writes_the_pdf_only_to_storage(
    engine: Engine,
    sessions: sessionmaker[Session],
    store: MemoryStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mkc.extraction.fetch import fetch_document
    from mkc.extraction.storage import LOCAL_CACHE_DIR

    cache = Path(LOCAL_CACHE_DIR)
    before = sorted(cache.rglob("*")) if cache.exists() else []
    monkeypatch.chdir(tmp_path)
    pdf = make_pdf(berlin_pages(["1"]))
    fetch_document(
        OPERATOR_ID,
        sessions=sessions,
        store=store,
        get=FakeGet([(URL_OK, pdf)]),
        operators=operators(),
    )
    assert list(store.data.values()) == [pdf]
    assert store.puts == 1
    assert list(tmp_path.iterdir()) == [], "the PDF must not be written to local disk"
    after = sorted(cache.rglob("*")) if cache.exists() else []
    assert after == before, "fetch_document must not write the local cache when given a store"
    assert rows(engine, "select count(*) from blob") == [(0,)], "no PDF in the Postgres blob table"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.parametrize("name", ["catalogue.pdf", "0123abcd", "nested/page-3.png"])
def test_local_cache_dir_is_gitignored(name: str) -> None:
    from mkc.extraction.storage import LOCAL_CACHE_DIR

    cache = Path(LOCAL_CACHE_DIR).resolve()
    assert cache.is_relative_to(REPO), f"{cache} is outside the repo"
    target = (cache / name).relative_to(REPO).as_posix()
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", target], cwd=REPO, check=False
    )
    assert result.returncode == 0, f"{target} is not gitignored"


def test_the_cli_caches_pdfs_in_storage_when_it_is_configured() -> None:
    # Mutation pass: `mkc run start --operator` must use Supabase Storage when the settings
    # name it, not the local cache.
    from mkc.cli import make_documents
    from mkc.config import Settings
    from mkc.harness.storage import StorageBlobStore

    storage = {
        "storage_s3_endpoint": "https://p.storage.supabase.co/storage/v1/s3",
        "storage_s3_region": "eu-west-1",
        "storage_bucket": "mkc-storage",
        "storage_access_key_id": "id",
        "storage_secret_access_key": "secret",
    }
    docs = make_documents(Settings(**storage), sessionmaker())
    assert isinstance(docs.store, StorageBlobStore)
