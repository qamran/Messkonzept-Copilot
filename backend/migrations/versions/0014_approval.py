"""Table approval: the approval queue, one row per queued draft (MKC-23.3, decision 83).

Additive only (decision 48). `draft_id` is unique, so a draft is queued at most once; the
harness's `enqueue_approval` upserts on it. Decision columns come with MKC-29.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("draft_id", sa.BigInteger(), sa.ForeignKey("draft.id"), nullable=False,
                  unique=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("approval")
