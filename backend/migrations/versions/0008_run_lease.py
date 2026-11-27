"""Run lease columns: the worker that holds a run and until when (MKC-17.1, decision 57).

Additive only (decision 48): two nullable columns. A free run has both empty.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run", sa.Column("lease_owner", sa.Text(), nullable=True))
    op.add_column("run", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("run", "lease_expires_at")
    op.drop_column("run", "lease_owner")
