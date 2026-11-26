"""ORM models. Each table also has an Alembic migration; a test checks they match."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mkc.db.base import Base

BACKUP_STATES = ("running", "ok", "failed")


class BackupRun(Base):
    """One run of `mkc-backup` (MKC-11): written at the start, updated at the end.

    A run that stays `running` was killed; the status endpoint reports it as stale.
    """

    __tablename__ = "backup_runs"
    __table_args__ = (
        CheckConstraint("state IN ('running', 'ok', 'failed')", name="ck_backup_runs_state"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16))
    # The object's name in the bucket (never the upload link).
    object_name: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    # Error class and a short message with secrets removed.
    error: Mapped[str | None] = mapped_column(Text)
