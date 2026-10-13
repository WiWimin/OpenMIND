"""meeting_records table

Revision ID: 0007_meeting_records
Revises: 0005_meeting_materials
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_meeting_records"
down_revision: str | None = "0005_meeting_materials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_records",
        sa.Column("record_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(length=40),
            sa.ForeignKey("meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column(
            "source_material_id",
            sa.String(length=40),
            sa.ForeignKey("meeting_materials.material_id"),
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
    op.create_index("ix_meeting_records_meeting_id", "meeting_records", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_records_meeting_id", table_name="meeting_records")
    op.drop_table("meeting_records")
