"""meeting_minutes and action_items tables

Revision ID: 0008_minutes_action_items
Revises: 0007_meeting_records
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_minutes_action_items"
down_revision: str | None = "0007_meeting_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_minutes",
        sa.Column("minutes_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "source_record_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
    op.create_index("ix_meeting_minutes_meeting_id", "meeting_minutes", ["meeting_id"])

    op.create_table(
        "action_items",
        sa.Column("action_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("assignee", sa.String(length=100), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending_confirmation",
        ),
        sa.Column(
            "source_record_id",
            sa.String(length=40),
            sa.ForeignKey("meeting_records.record_id"),
            nullable=True,
        ),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
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
    op.create_index("ix_action_items_meeting_id", "action_items", ["meeting_id"])
    op.create_index("ix_action_items_meeting_status", "action_items", ["meeting_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_action_items_meeting_status", table_name="action_items")
    op.drop_index("ix_action_items_meeting_id", table_name="action_items")
    op.drop_table("action_items")
    op.drop_index("ix_meeting_minutes_meeting_id", table_name="meeting_minutes")
    op.drop_table("meeting_minutes")
