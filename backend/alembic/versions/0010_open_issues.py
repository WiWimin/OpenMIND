"""open_issues table

Revision ID: 0010_open_issues
Revises: 0009_personal_tasks
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_open_issues"
down_revision: str | None = "0009_personal_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "open_issues",
        sa.Column("issue_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("follow_up", sa.Text(), nullable=True),
        sa.Column(
            "source_record_id",
            sa.String(length=40),
            sa.ForeignKey("meeting_records.record_id"),
            nullable=True,
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
    op.create_index("ix_open_issues_meeting_id", "open_issues", ["meeting_id"])
    op.create_index("ix_open_issues_meeting_status", "open_issues", ["meeting_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_open_issues_meeting_status", table_name="open_issues")
    op.drop_index("ix_open_issues_meeting_id", table_name="open_issues")
    op.drop_table("open_issues")
