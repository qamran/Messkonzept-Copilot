"""Tables run, item and turn: the harness queue and its turns (MKC-15).

Additive only (decision 48). The state columns have no CHECK constraint: MKC-17 adds a run
state, and `mkc.harness.states.transition` is the guard (decision 54).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _times() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    ]  # fmt: skip


def upgrade() -> None:
    op.create_table(
        "run",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        *_times(),
    )
    op.create_table(
        "item",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("run.id"), nullable=False),
        sa.Column("concept_key", sa.Text(), nullable=False),
        sa.Column("document_hash", sa.Text(), nullable=False),
        sa.Column("task", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        *_times(),
        sa.UniqueConstraint("run_id", "concept_key", name="uq_item_run_concept"),
    )
    op.create_index("ix_item_run_state", "item", ["run_id", "state"])
    op.create_table(
        "turn",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("assistant", postgresql.JSONB(), nullable=False),
        sa.Column("tool_results", postgresql.JSONB(), nullable=False),
        sa.Column("cost_eur", sa.Numeric(12, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("item_id", "number", name="uq_turn_item_number"),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("turn")
    op.drop_index("ix_item_run_state", table_name="item")
    op.drop_table("item")
    op.drop_table("run")
