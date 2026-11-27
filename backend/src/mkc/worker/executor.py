"""The run executor (MKC-17.2, decision 57): claims a run with a lease and processes it."""

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings
from mkc.harness.tools import ToolRegistry
from mkc.models.client import ModelClient
from mkc.worker.lease import claim_run

__all__ = ["Executor", "claim_run"]


class Executor:
    def __init__(
        self,
        settings: Settings,
        *,
        sessions: sessionmaker[Session],
        client_factory: Callable[[], ModelClient],
        registry: ToolRegistry | None = None,
        owner: str | None = None,
    ) -> None:
        raise NotImplementedError

    def __enter__(self) -> "Executor":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def run_once(self) -> bool:
        raise NotImplementedError

    def graceful_shutdown(self) -> None:
        raise NotImplementedError
