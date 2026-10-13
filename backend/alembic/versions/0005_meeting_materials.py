"""meeting_materials table

Revision ID: 0005_meeting_materials
Revises: 0004_meetings
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_meeting_materials"
down_revision: str | None = "0004_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_materials",
        sa.Column("material_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=20),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_meeting_materials_meeting_id", "meeting_materials", ["meeting_id"])
    op.create_index("ix_meeting_materials_user_id", "meeting_materials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_materials_user_id", table_name="meeting_materials")
    op.drop_index("ix_meeting_materials_meeting_id", table_name="meeting_materials")
    op.drop_table("meeting_materials")
