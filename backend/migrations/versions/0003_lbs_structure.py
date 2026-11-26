"""Table lbs_structure: LBS reference data from the BDEW Codeliste (MKC-12).

Additive only (decision 48). Filled by `mkc-load-lbs` from backend/data/lbs_structures.yaml
(decision 50).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lbs_structure",
        sa.Column("code", sa.String(13), primary_key=True),
        sa.Column("bezeichnung", sa.Text(), nullable=False),
        sa.Column("objects", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lbs_structure")
