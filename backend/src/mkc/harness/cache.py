"""Tool-result cache for deterministic document tools (MKC-16.4, design 8.3, decision 56).

Key: (tool, code version, sha256 of the validated arguments, document hash). A new commit
misses, so a fixed tool never serves its old result. Only `ok` results are stored, and each
write commits on its own: the hits on resume come from a turn that never got its checkpoint.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mkc.db.models import ToolCacheRow


@dataclass(frozen=True)
class Cached:
    """A cache hit; `data` may be None."""

    data: Any


class ToolCache:
    def __init__(self, session: Session, code_version: str) -> None:
        self._session = session
        self._code_version = code_version

    def get(self, tool: str, args: dict[str, Any], document_hash: str) -> Cached | None:
        statement = select(ToolCacheRow.data).where(
            ToolCacheRow.tool == tool,
            ToolCacheRow.code_version == self._code_version,
            ToolCacheRow.args_hash == args_hash(args),
            ToolCacheRow.document_hash == document_hash,
        )
        rows = self._session.execute(statement).all()
        return Cached(rows[0].data) if rows else None

    def put(self, tool: str, args: dict[str, Any], document_hash: str, data: Any) -> None:
        """Store an `ok` result and commit: the session must hold nothing else."""
        row = {
            "tool": tool,
            "code_version": self._code_version,
            "args_hash": args_hash(args),
            "document_hash": document_hash,
            "data": data,
        }
        self._session.execute(insert(ToolCacheRow).values(row).on_conflict_do_nothing())
        self._session.commit()


def args_hash(args: dict[str, Any]) -> str:
    """sha256 of the canonical JSON of the validated arguments."""
    text = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()
