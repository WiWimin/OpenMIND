"""drop user-level embedding config

向量模型收归服务端统一配置（docker/.env EMBEDDING_*），用户不再自备
Embedding；删除 user_model_configs 中的 embedding 相关字段。

Revision ID: 0020_drop_user_embedding
Revises: 0019_meeting_templates
Create Date: 2026-10-31

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_drop_user_embedding"
down_revision: str | None = "0019_meeting_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user_model_configs", "embedding_api_base")
    op.drop_column("user_model_configs", "embedding_api_key_enc")
    op.drop_column("user_model_configs", "embedding_model")
    op.drop_column("user_model_configs", "embedding_dim")


def downgrade() -> None:
    op.add_column(
        "user_model_configs",
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_model_configs",
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "user_model_configs",
        sa.Column("embedding_api_key_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_model_configs",
        sa.Column("embedding_api_base", sa.String(length=255), nullable=True),
    )
