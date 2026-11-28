"""Table gold_item: gold items with their provenance (MKC-24.2, decisions 88 and 89).

Additive only (decision 48). One drafted item and at most one blind label per (kind, key):
unique on (kind, key, blind). A blind label never has a drafter.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gold_item",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("split", sa.String(8), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("drafted_by", sa.Text(), nullable=True),
        sa.Column("verified_by", sa.Text(), nullable=True),
        sa.Column("blind", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("kind", "key", "blind", name="uq_gold_item_kind_key_blind"),
        sa.CheckConstraint("split IN ('dev', 'test')", name="ck_gold_item_split"),
        sa.CheckConstraint("NOT blind OR drafted_by IS NULL",
                           name="ck_gold_item_blind_no_drafter"),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("gold_item")
