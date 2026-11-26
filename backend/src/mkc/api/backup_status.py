"""Backup status for admins (MKC-11.3): `GET /api/admin/backup-status`.

`stale` is true when there is no successful backup newer than MKC_BACKUP_STALE_HOURS
(default 26 h: one nightly run plus margin). It also catches a CronJob that never starts,
which leaves no row at all. The Runs page shows this later.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, select

from mkc.db.models import BackupRun

BackupState = Literal["running", "ok", "failed"]


class BackupRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    finished_at: datetime | None = None
    state: BackupState
    object_name: str | None = None
    size_bytes: int | None = None
    error: str | None = None


class BackupStatus(BaseModel):
    state: Literal["never", "running", "ok", "failed"]
    last_run: BackupRunOut | None
    last_success: BackupRunOut | None
    stale: bool


LatestRuns = tuple[BackupRunOut | None, BackupRunOut | None]


def load_latest(engine: Engine) -> LatestRuns:
    """(latest run, latest successful run) from `backup_runs`."""
    newest = BackupRun.started_at.desc()
    with engine.connect() as conn:
        last = conn.execute(select(BackupRun).order_by(newest).limit(1)).first()
        good = conn.execute(
            select(BackupRun).where(BackupRun.state == "ok").order_by(newest).limit(1)
        ).first()
    return (
        BackupRunOut.model_validate(last, from_attributes=True) if last else None,
        BackupRunOut.model_validate(good, from_attributes=True) if good else None,
    )


def latest_backup_runs() -> Callable[[], LatestRuns]:
    """FastAPI dependency: the loader (tests replace it; no database at import time)."""
    from mkc.db.session import get_engine

    return lambda: load_latest(get_engine())


def summarize(
    last_run: BackupRunOut | None,
    last_success: BackupRunOut | None,
    stale_hours: float,
    now: datetime | None = None,
) -> BackupStatus:
    now = now or datetime.now(UTC)
    fresh = last_success is not None and (
        now - (last_success.finished_at or last_success.started_at)
    ) <= timedelta(hours=stale_hours)
    return BackupStatus(
        state=last_run.state if last_run else "never",
        last_run=last_run,
        last_success=last_success,
        stale=not fresh,
    )
