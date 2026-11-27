"""Tool-result cache for deterministic document tools (MKC-16.4, design 8.3, decision 56).

Key: (tool, code version, sha256 of the validated arguments, document hash). A new commit
misses, so a fixed tool never serves its old result. Only `ok` results are stored, and each
write commits on its own: the hits on resume come from a turn that never got its checkpoint.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Cached:
    """A cache hit; `data` may be None."""

    data: Any


class ToolCache:
    def __init__(self, session: Session, code_version: str) -> None:
        self._session = session
        self._code_version = code_version

    def get(self, tool: str, args: dict[str, Any], document_hash: str) -> Cached | None:
        raise NotImplementedError

    def put(self, tool: str, args: dict[str, Any], document_hash: str, data: Any) -> None:
        raise NotImplementedError
