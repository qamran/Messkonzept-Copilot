"""Tables operator and source_document (MKC-21, decisions 62 and 63).

Additive only (decision 48). No byte columns: the PDF lives in Supabase Storage under the
ref `blob:sha256:<sha256>`, never in Postgres.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operator",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("voltage_level", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("edition", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )  # fmt: skip
    op.create_table(
        "source_document",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("operator_id", sa.Text(), sa.ForeignKey("operator.id"), nullable=False),
        sa.Column("edition", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("operator_id", "edition", name="uq_source_document_edition"),
    )  # fmt: skip
    op.create_index("ix_source_document_sha256", "source_document", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_source_document_sha256", table_name="source_document")
    op.drop_table("source_document")
    op.drop_table("operator")
