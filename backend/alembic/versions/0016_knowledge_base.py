"""personal knowledge base

Revision ID: 0016_knowledge_base
Revises: 0015_purpose_models
Create Date: 2026-10-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0016_knowledge_base"
down_revision: str | None = "0015_purpose_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=20),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_knowledge_documents_user_id", "knowledge_documents", ["user_id"]
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(length=40), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=40),
            sa.ForeignKey("knowledge_documents.document_id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunks_document_index",
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_user_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
