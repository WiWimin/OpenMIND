"""user_model_configs table

Revision ID: 0012_user_model_configs
Revises: 0011_document_chunks
Create Date: 2026-10-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_user_model_configs"
down_revision: str | None = "0011_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_model_configs",
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.user_id"),
            primary_key=True,
        ),
        sa.Column("llm_api_base", sa.String(length=255), nullable=True),
        sa.Column("llm_api_key_enc", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_api_base", sa.String(length=255), nullable=True),
        sa.Column("embedding_api_key_enc", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
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


def downgrade() -> None:
    op.drop_table("user_model_configs")
