"""Limit columns: when a run started and how often an item resumed without progress
(MKC-18.1, decision 58).

Additive only (decision 48): a nullable column and a column with a server default.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "item",
        sa.Column("attempts_without_progress", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("item", "attempts_without_progress")
    op.drop_column("run", "started_at")
