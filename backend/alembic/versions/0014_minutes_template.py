"""minutes template

Revision ID: 0014_minutes_template
Revises: 0013_record_markers_sources
Create Date: 2026-10-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_minutes_template"
down_revision: str | None = "0013_record_markers_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meeting_minutes",
        sa.Column(
            "template",
            sa.String(length=20),
            nullable=False,
            server_default="standard",
        ),
    )


def downgrade() -> None:
    op.drop_column("meeting_minutes", "template")
