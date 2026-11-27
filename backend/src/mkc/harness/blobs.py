"""Content-addressed blob storage for large tool outputs (MKC-16.2, decision 56).

A ref is `blob:sha256:<hex>`. `DbBlobStore` keeps blobs in the Postgres table `blob`, in the
caller's transaction; MKC-21 adds a Supabase Storage store. Refs stay valid across the swap.
"""

import hashlib
from typing import Protocol

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mkc.db.models import Blob

PREFIX = "blob:sha256:"


class BlobStore(Protocol):
    def put(self, data: bytes) -> str:
        """Store `data` (idempotent) and return its ref."""
        ...

    def get(self, ref: str) -> bytes:
        """The data of `ref`; `KeyError` if there is none."""
        ...


class DbBlobStore:
    """Blobs in the table `blob`. Writes join the session's transaction; nothing commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        row = {"sha256": digest, "data": data, "size": len(data)}
        self._session.execute(insert(Blob).values(row).on_conflict_do_nothing())
        return PREFIX + digest

    def get(self, ref: str) -> bytes:
        blob = self._session.get(Blob, ref.removeprefix(PREFIX)) if ref.startswith(PREFIX) else None
        if blob is None:
            raise KeyError(ref)
        return blob.data
