"""personal_tasks table

Revision ID: 0009_personal_tasks
Revises: 0008_minutes_action_items
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_personal_tasks"
down_revision: str | None = "0008_minutes_action_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_tasks",
        sa.Column("task_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=True,
        ),
        sa.Column(
            "action_id",
            sa.String(length=40),
            sa.ForeignKey("action_items.action_id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="todo"),
        sa.Column("due_date", sa.Date(), nullable=True),
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
    op.create_index("ix_personal_tasks_user_id", "personal_tasks", ["user_id"])
    op.create_index("ix_personal_tasks_meeting_id", "personal_tasks", ["meeting_id"])
    op.create_index(
        "ix_personal_tasks_user_status_due",
        "personal_tasks",
        ["user_id", "status", "due_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_personal_tasks_user_status_due", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_meeting_id", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_user_id", table_name="personal_tasks")
    op.drop_table("personal_tasks")
