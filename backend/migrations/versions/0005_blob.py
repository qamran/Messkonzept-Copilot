"""Table blob: content-addressed storage for large tool outputs (MKC-16.2, decision 56).

Additive only (decision 48). Interim store until MKC-21 adds Supabase Storage.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blob",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("blob")
