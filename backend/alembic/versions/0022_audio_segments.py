"""audio live segments

Revision ID: 0022_audio_segments
Revises: 0021_template_category_default
Create Date: 2026-10-31

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_audio_segments"
down_revision: str | None = "0021_template_category_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meeting_audio",
        sa.Column("segments", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meeting_audio", "segments")
