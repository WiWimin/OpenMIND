"""record markers and minutes material sources

Revision ID: 0013_record_markers_sources
Revises: 0012_user_model_configs
Create Date: 2026-10-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_record_markers_sources"
down_revision: str | None = "0012_user_model_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meeting_records",
        sa.Column("marker_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "meeting_minutes",
        sa.Column(
            "source_material_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("meeting_minutes", "source_material_ids")
    op.drop_column("meeting_records", "marker_type")
