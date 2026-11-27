"""The real `save_draft`: one draft per (document hash, concept key) (MKC-16.5, decision 56).

The key comes from the harness's `ToolEnv`, never from the model's arguments. A second save
for the same key replaces the body and keeps one row. `commit_record` (MKC-29/30) uses the
same `record_key`. A draft row can outlive a failed item: go by the item state, not the row.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.tools import ToolEnv


def record_key(env: ToolEnv) -> tuple[str, str]:
    """(document hash, concept key): the idempotency key of a draft and of its commit."""
    raise NotImplementedError


def make_save_draft(sessions: sessionmaker[Session]) -> Callable[[BaseModel, ToolEnv], Any]:
    """`save_draft` writing through its own short transaction from `sessions`."""
    raise NotImplementedError
