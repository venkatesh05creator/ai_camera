"""Alembic 0005: people + face_templates (+ event face labels).

Face templates are AES-256-GCM encrypted at rest with the biometric key;
consent is enforced server-side (see people_service).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_people"
down_revision = "0004_cameras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("consent_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_statement_hash", sa.String(length=64),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "face_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("embedding_encrypted", sa.Text(), nullable=False),
        sa.Column("samples_count", sa.Integer(), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id"),
    )

    # face labels on camera events: encrypted JSON
    # {"known":[{"person_id": 3, "name": "Venki", "score": 0.52}],
    #  "unknown_faces": 1}
    op.add_column("camera_events",
                  sa.Column("labels_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("camera_events", "labels_encrypted")
    op.drop_table("face_templates")
    op.drop_table("people")
