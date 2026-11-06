"""Alembic 0002: provider_usage (quota meter)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_provider_usage"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model", "day", name="uq_usage_pmd"),
    )
    op.create_index("ix_usage_provider_day", "provider_usage",
                    ["provider", "day"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_provider_day", table_name="provider_usage")
    op.drop_table("provider_usage")
