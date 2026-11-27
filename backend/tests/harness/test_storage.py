"""MKC-21.4: the Supabase Storage `BlobStore` (S3 protocol), with no network.

The SigV4 vectors were made with botocore's `S3SigV4Auth` (same keys, URL, payload and
time); the store must sign byte for byte the same.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mkc.harness.blobs import PREFIX

ENDPOINT = "https://proj.storage.supabase.co/storage/v1/s3"
KEY_ID = "AKIDEXAMPLE"
SECRET = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
WHEN = datetime(2026, 11, 27, 19, 51, 54, tzinfo=UTC)
HEX = "ab" * 32
CREDENTIAL = f"Credential={KEY_ID}/20261127/eu-west-1/s3/aws4_request"
SIGNED = "SignedHeaders=host;x-amz-content-sha256;x-amz-date"
PUT_SIG = "b15ae464869e70ccd41bfb946bdb35a5b70ba292be150f35f4f4940bfe4f0042"
GET_SIG = "c0d8d4438791531581307ab204361fc3ca601889602d2ce40eb060548a98d269"


def test_sigv4_matches_botocore() -> None:
    from mkc.harness.storage import sigv4_headers

    url = f"{ENDPOINT}/mkc-storage/sha256/{HEX}"
    for method, body, sig in (("PUT", b"hello pdf", PUT_SIG), ("GET", b"", GET_SIG)):
        headers = sigv4_headers(
            method, url, hashlib.sha256(body).hexdigest(),
            key_id=KEY_ID, secret=SECRET, region="eu-west-1", now=WHEN,
        )  # fmt: skip
        assert headers["x-amz-date"] == "20261127T195154Z"
        assert headers["authorization"] == (
            f"AWS4-HMAC-SHA256 {CREDENTIAL}, {SIGNED}, Signature={sig}"
        )


class FakeBucket:
    """An S3 bucket behind `httpx.MockTransport`: PUT and GET by path."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.headers["authorization"].startswith("AWS4-HMAC-SHA256 ")
        path = request.url.path
        if request.method == "PUT":
            body = request.read()
            assert request.headers["x-amz-content-sha256"] == hashlib.sha256(body).hexdigest()
            self.objects[path] = body
            return httpx.Response(200)
        if request.method == "GET" and path in self.objects:
            return httpx.Response(200, content=self.objects[path])
        return httpx.Response(404, content=b"<Error><Code>NoSuchKey</Code></Error>")


def _store(bucket: FakeBucket) -> Any:
    from mkc.harness.storage import StorageBlobStore

    return StorageBlobStore(
        endpoint=ENDPOINT, region="eu-west-1", bucket="mkc-storage", key_id=KEY_ID,
        secret=SecretStr(SECRET), transport=httpx.MockTransport(bucket),
    )  # fmt: skip


def test_put_and_get_round_trip_under_a_content_address() -> None:
    from mkc.harness.storage import StorageBlobStore

    bucket = FakeBucket()
    store = _store(bucket)
    assert isinstance(store, StorageBlobStore)
    data = b"%PDF-1.7 some bytes"
    digest = hashlib.sha256(data).hexdigest()
    assert store.put(data) == PREFIX + digest
    assert list(bucket.objects) == [f"/storage/v1/s3/mkc-storage/sha256/{digest}"]
    assert store.get(PREFIX + digest) == data


def test_get_of_a_missing_object_is_a_key_error() -> None:
    store = _store(FakeBucket())
    with pytest.raises(KeyError):
        store.get(PREFIX + HEX)


@pytest.mark.parametrize("ref", ["blob:sha256:../x", "sha256:" + HEX, PREFIX + "AB" * 32])
def test_a_malformed_ref_is_a_key_error_and_never_requested(ref: str) -> None:
    bucket = FakeBucket()
    with pytest.raises(KeyError):
        _store(bucket).get(ref)
    assert bucket.requests == []


def test_a_server_error_is_raised_not_hidden() -> None:
    from mkc.harness.storage import StorageBlobStore

    store = StorageBlobStore(
        endpoint=ENDPOINT, region="eu-west-1", bucket="b", key_id=KEY_ID,
        secret=SecretStr(SECRET), transport=httpx.MockTransport(lambda r: httpx.Response(500)),
    )  # fmt: skip
    with pytest.raises(httpx.HTTPStatusError):
        store.put(b"x")
    with pytest.raises(httpx.HTTPStatusError):
        store.get(PREFIX + HEX)


def test_the_secret_is_not_in_the_store_repr() -> None:
    assert SECRET not in repr(_store(FakeBucket()))


def test_layered_store_writes_the_primary_and_reads_old_refs_from_the_fallback() -> None:
    from mkc.harness.storage import LayeredBlobStore
    from tests.extraction.conftest import MemoryStore

    primary, old = MemoryStore(), MemoryStore()
    old_ref = old.put(b"from the blob table")
    store = LayeredBlobStore(primary, old)
    new_ref = store.put(b"new turn result")
    assert new_ref in primary.data and new_ref not in old.data
    assert store.get(old_ref) == b"from the blob table"
    assert store.get(new_ref) == b"new turn result"
    with pytest.raises(KeyError):
        store.get(PREFIX + HEX)


def test_file_store_keeps_blobs_under_its_root(tmp_path: Path) -> None:
    from mkc.harness.storage import FileBlobStore

    store = FileBlobStore(tmp_path / "cache")
    ref = store.put(b"local pdf")
    assert store.get(ref) == b"local pdf"
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [ref.removeprefix(PREFIX)]
    with pytest.raises(KeyError):
        store.get(PREFIX + HEX)
    with pytest.raises(KeyError):
        store.get("blob:sha256:../../etc/passwd")


def _settings(**env: str) -> Any:
    from mkc.config import Settings

    return Settings(**env)


def test_storage_from_settings_needs_all_five_or_none() -> None:
    from mkc.harness.storage import StorageBlobStore, StorageNotConfigured, storage_from_settings

    full = {
        "storage_s3_endpoint": ENDPOINT,
        "storage_s3_region": "eu-west-1",
        "storage_bucket": "mkc-storage",
        "storage_access_key_id": KEY_ID,
        "storage_secret_access_key": SECRET,
    }
    assert storage_from_settings(_settings()) is None
    assert isinstance(storage_from_settings(_settings(**full)), StorageBlobStore)
    with pytest.raises(StorageNotConfigured, match="storage_bucket"):
        storage_from_settings(_settings(**{**full, "storage_bucket": ""}))


def test_settings_do_not_show_the_storage_secret() -> None:
    settings = _settings(storage_secret_access_key=SECRET)
    assert SECRET not in repr(settings)
