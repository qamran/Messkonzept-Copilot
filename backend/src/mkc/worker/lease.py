"""The run lease (MKC-17.1, decision 57): one worker holds a run at a time."""

from sqlalchemy.orm import Session

from mkc.db.models import Run


class LeaseLost(Exception):
    """This worker no longer holds the run's lease."""


def claim_run(session: Session, *, owner: str, lease_seconds: float) -> Run | None:
    raise NotImplementedError


def renew_lease(session: Session, run_id: int, *, owner: str, lease_seconds: float) -> bool:
    raise NotImplementedError


def release_lease(session: Session, run_id: int, *, owner: str) -> None:
    raise NotImplementedError


def fence(session: Session, run_id: int, *, owner: str) -> None:
    raise NotImplementedError
