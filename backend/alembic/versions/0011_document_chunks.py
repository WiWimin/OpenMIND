"""document_chunks table

Revision ID: 0011_document_chunks
Revises: 0010_open_issues
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0011_document_chunks"
down_revision: str | None = "0010_open_issues"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "material_id",
            sa.String(length=40),
            sa.ForeignKey("meeting_materials.material_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "material_id", "chunk_index", name="uq_document_chunks_material_index"
        ),
    )
    op.create_index("ix_document_chunks_material_id", "document_chunks", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_material_id", table_name="document_chunks")
    op.drop_table("document_chunks")
