"""template category, text-created templates and default template id

模板管理改版：
- meeting_templates 增加 category（会前/会后/通用）；
- file_name / storage_key 放宽为可空（支持纯文本创建的模板，无源文件）；
- user_memory.preferred_minutes_template 放宽到 64 字符，
  允许存放模板 id（tpl_ 前缀，36 字符）而不仅是内置枚举值。

Revision ID: 0021_template_category_default
Revises: 0020_drop_user_embedding
Create Date: 2026-10-31

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_template_category_default"
down_revision: str | None = "0020_drop_user_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meeting_templates",
        sa.Column("category", sa.String(length=20), nullable=True),
    )
    op.alter_column("meeting_templates", "file_name", existing_type=sa.String(255), nullable=True)
    op.alter_column("meeting_templates", "storage_key", existing_type=sa.Text(), nullable=True)
    op.alter_column(
        "user_memories",
        "preferred_minutes_template",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
    )


def downgrade() -> None:
    op.alter_column(
        "user_memories",
        "preferred_minutes_template",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
    )
    op.alter_column("meeting_templates", "storage_key", existing_type=sa.Text(), nullable=False)
    op.alter_column(
        "meeting_templates", "file_name", existing_type=sa.String(255), nullable=False
    )
    op.drop_column("meeting_templates", "category")
