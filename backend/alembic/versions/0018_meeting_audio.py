"""meeting audio transcription

Revision ID: 0018_meeting_audio
Revises: 0017_user_memory
Create Date: 2026-10-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_meeting_audio"
down_revision: str | None = "0017_user_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_audio",
        sa.Column("audio_id", sa.String(length=40), primary_key=True),
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
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "record_id",
            sa.String(length=40),
            sa.ForeignKey("meeting_records.record_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_meeting_audio_meeting_id", "meeting_audio", ["meeting_id"])
    op.create_index("ix_meeting_audio_user_id", "meeting_audio", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_audio_user_id", table_name="meeting_audio")
    op.drop_index("ix_meeting_audio_meeting_id", table_name="meeting_audio")
    op.drop_table("meeting_audio")
