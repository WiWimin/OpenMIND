"""user memory profile

Revision ID: 0017_user_memory
Revises: 0016_knowledge_base
Create Date: 2026-10-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_user_memory"
down_revision: str | None = "0016_knowledge_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column(
            "user_id",
            sa.String(length=40),
            sa.ForeignKey("users.user_id"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("work_scenarios", sa.Text(), nullable=True),
        sa.Column("communication_style", sa.Text(), nullable=True),
        sa.Column("preferred_minutes_template", sa.String(length=20), nullable=True),
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


def downgrade() -> None:
    op.drop_table("user_memories")
