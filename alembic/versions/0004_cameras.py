"""Alembic 0004: cameras registry, health, events, notifications, nonces."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_cameras"
down_revision = "0003_memory_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cameras_kind", "cameras", ["kind"], unique=False)

    op.create_table(
        "camera_health",
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_frame_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("frames", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("camera_id"),
    )

    op.create_table(
        "camera_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("person_count", sa.Integer(), nullable=False),
        sa.Column("motion_score", sa.Float(), nullable=False),
        sa.Column("snapshot_encrypted", sa.Text(), nullable=True),
        sa.Column("snapshot_status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_camera_events_cam_ts", "camera_events",
                    ["camera_id", "ts"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_unread", "notifications",
                    ["is_read", "ts"], unique=False)

    op.create_table(
        "ingest_nonces",
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index("ix_ingest_nonces_cam", "ingest_nonces",
                    ["camera_id"], unique=False)


def downgrade() -> None:
    op.drop_table("ingest_nonces")
    op.drop_table("notifications")
    op.drop_table("camera_events")
    op.drop_table("camera_health")
    op.drop_table("cameras")
