"""Alembic 0003: memory_items (encrypted memory)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_memory_items"
down_revision = "0002_provider_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("text_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_kind", "memory_items", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memory_kind", table_name="memory_items")
    op.drop_table("memory_items")
