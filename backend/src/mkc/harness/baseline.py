"""Baseline memory: what the simple loop keeps in memory instead of the database (MKC-20)."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session


@dataclass
class RunMemory:
    run_id: int
    approvals: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, session: Session, run_id: int) -> "RunMemory":
        return cls(run_id)
