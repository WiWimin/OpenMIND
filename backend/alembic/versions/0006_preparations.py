"""preparations table

Revision ID: 0006_preparations
Revises: 0005_meeting_materials
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_preparations"
down_revision: str | None = "0005_meeting_materials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "preparations",
        sa.Column("preparation_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "checklist",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
    op.create_index("ix_preparations_meeting_id", "preparations", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("ix_preparations_meeting_id", table_name="preparations")
    op.drop_table("preparations")
