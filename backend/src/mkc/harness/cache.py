"""Tool-result cache for deterministic document tools (MKC-16.4, design 8.3, decision 56).

Key: (tool, code version, sha256 of the validated arguments, document hash). A new commit
misses, so a fixed tool never serves its old result. Only `ok` results are stored, and each
write commits on its own, in its own session: the hits on resume come from a turn that never
got its checkpoint, and a write never commits the loop's pending rows.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import ToolCacheRow


@dataclass(frozen=True)
class Cached:
    """A cache hit; `data` may be None."""

    data: Any


class ToolCache:
    """Reads and writes through short sessions of its own, never the caller's."""

    def __init__(self, sessions: sessionmaker[Session], code_version: str) -> None:
        self._sessions = sessions
        self._code_version = code_version

    def get(self, tool: str, args: dict[str, Any], document_hash: str) -> Cached | None:
        statement = select(ToolCacheRow.data).where(
            ToolCacheRow.tool == tool,
            ToolCacheRow.code_version == self._code_version,
            ToolCacheRow.args_hash == args_hash(args),
            ToolCacheRow.document_hash == document_hash,
        )
        with self._sessions() as session:
            rows = session.execute(statement).all()
        return Cached(rows[0].data) if rows else None

    def put(self, tool: str, args: dict[str, Any], document_hash: str, data: Any) -> None:
        """Store an `ok` result and commit it at once (first write wins)."""
        row = {
            "tool": tool,
            "code_version": self._code_version,
            "args_hash": args_hash(args),
            "document_hash": document_hash,
            "data": data,
        }
        with self._sessions.begin() as session:
            session.execute(insert(ToolCacheRow).values(row).on_conflict_do_nothing())


def args_hash(args: dict[str, Any]) -> str:
    """sha256 of the canonical JSON of the validated arguments."""
    text = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()
