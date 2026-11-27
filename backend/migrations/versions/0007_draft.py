"""Table draft: one draft per (document hash, concept key) (MKC-16.5, decision 56).

Additive only (decision 48). The unique key is `save_draft`'s idempotency key.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("document_hash", sa.Text(), nullable=False),
        sa.Column("concept_key", sa.Text(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("document_hash", "concept_key", name="uq_draft_record_key"),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("draft")
