"""The run's harness mode (MKC-20, decision 60).

Additive only (decision 48): one column with a server default, so every earlier run reads as
a full-mode run.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run", sa.Column("mode", sa.String(16), server_default="full", nullable=False))


def downgrade() -> None:
    op.drop_column("run", "mode")
