"""parse_error_code for material / knowledge document

Revision ID: 0023_parse_error_code
Revises: 0022_audio_segments
Create Date: 2026-11-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_parse_error_code"
down_revision: str | None = "0022_audio_segments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meeting_materials",
        sa.Column("parse_error_code", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("parse_error_code", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "parse_error_code")
    op.drop_column("meeting_materials", "parse_error_code")
