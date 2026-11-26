"""Table backup_runs: one row per run of mkc-backup (MKC-11).

Additive only (decision 48): `helm rollback` does not undo a migration, so the previous
release must keep working on the new schema.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("object_name", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("state IN ('running', 'ok', 'failed')", name="ck_backup_runs_state"),
    )
    op.create_index("ix_backup_runs_started_at", "backup_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_backup_runs_started_at", table_name="backup_runs")
    op.drop_table("backup_runs")
