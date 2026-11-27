"""Tracing: the run's Langfuse trace id and the `run_log` table (MKC-19, decision 59).

Additive only (decision 48): a nullable column and a new table. `run_log` has no foreign
keys: an insert would take `FOR KEY SHARE` on the run row and wait for the `FOR UPDATE` of
`fence`; a log must never wait for, or block, the loop.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run", sa.Column("trace_id", sa.Text(), nullable=True))
    op.create_table(
        "run_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("step", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(16), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_eur", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_run_log_run_id_id", "run_log", ["run_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_run_log_run_id_id", table_name="run_log")
    op.drop_table("run_log")
    op.drop_column("run", "trace_id")
