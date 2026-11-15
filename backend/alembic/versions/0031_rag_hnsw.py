"""rag hnsw vector indexes

为两张分块表建立 HNSW 余弦距离索引，检索排序下沉 PostgreSQL
（`document_chunks.embedding <=> query`）。权限过滤仍在 SQL 前置，
配合应用层过采样（`RAG_ANN_OVERSAMPLE`）补偿过滤召回损失。

索引构建参数 m / ef_construction 为建索引期常量；查询期 `hnsw.ef_search`
由 `RAG_HNSW_EF_SEARCH` 控制。数据量大时可用
`CREATE INDEX CONCURRENTLY` 在迁移外重建（Alembic 事务内不支持 CONCURRENTLY）。

Revision ID: 0031_rag_hnsw
Revises: 0030_rag_content_hash
Create Date: 2026-11-11

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0031_rag_hnsw"
down_revision: str | None = "0030_rag_content_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    ("ix_document_chunks_embedding_hnsw", "document_chunks"),
    ("ix_knowledge_chunks_embedding_hnsw", "knowledge_chunks"),
)


def upgrade() -> None:
    for index_name, table in _INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    for index_name, _table in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
