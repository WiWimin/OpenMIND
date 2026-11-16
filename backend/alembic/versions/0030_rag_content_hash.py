"""rag content hash & index fingerprint

增量索引：材料/知识库文档记录内容摘要与索引参数指纹，用于同用户同库内
复用同内容文件的分块（跳过解析与向量化）。存量行保持 NULL，不会被当作
复用源（旧向量产出参数未知），经 `scripts/reindex_all.py` 重建后回填。

Revision ID: 0030_rag_content_hash
Revises: 0029_job_queue
Create Date: 2026-11-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_rag_content_hash"
down_revision: str | None = "0029_job_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("meeting_materials", "knowledge_documents"):
        op.add_column(table, sa.Column("content_hash", sa.String(64), nullable=True))
        op.add_column(
            table, sa.Column("index_fingerprint", sa.String(64), nullable=True)
        )
        op.add_column(
            table,
            sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index(
        "ix_meeting_materials_user_content_hash",
        "meeting_materials",
        ["user_id", "content_hash"],
    )
    op.create_index(
        "ix_knowledge_documents_user_content_hash",
        "knowledge_documents",
        ["user_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_documents_user_content_hash", table_name="knowledge_documents"
    )
    op.drop_index(
        "ix_meeting_materials_user_content_hash", table_name="meeting_materials"
    )
    for table in ("knowledge_documents", "meeting_materials"):
        op.drop_column(table, "indexed_at")
        op.drop_column(table, "index_fingerprint")
        op.drop_column(table, "content_hash")
