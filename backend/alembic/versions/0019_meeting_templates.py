"""meeting templates for custom output structures

Revision ID: 0019_meeting_templates
Revises: 0018_meeting_audio
Create Date: 2026-10-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_meeting_templates"
down_revision: str | None = "0018_meeting_audio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_templates",
        sa.Column("template_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
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
    op.create_index("ix_meeting_templates_user_id", "meeting_templates", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_templates_user_id", table_name="meeting_templates")
    op.drop_table("meeting_templates")
