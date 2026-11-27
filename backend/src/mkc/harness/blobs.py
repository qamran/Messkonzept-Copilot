"""Content-addressed blob storage for large tool outputs (MKC-16.2, decision 56).

A ref is `blob:sha256:<hex>`. `DbBlobStore` keeps blobs in the Postgres table `blob`, in the
caller's transaction; MKC-21 adds a Supabase Storage store. Refs stay valid across the swap.
"""

from typing import Protocol

from sqlalchemy.orm import Session

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
        raise NotImplementedError

    def get(self, ref: str) -> bytes:
        raise NotImplementedError
