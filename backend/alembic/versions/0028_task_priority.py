"""personal_tasks priority field

个人任务优先级（M12 任务管理优化）：三色标签 high/medium/low 的数据源。
存量任务统一回填 medium。

Revision ID: 0028_task_priority
Revises: 0027_client_op_id
Create Date: 2026-11-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_task_priority"
down_revision: str | None = "0027_client_op_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "personal_tasks",
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="medium"),
    )
    op.create_check_constraint(
        "ck_personal_tasks_priority",
        "personal_tasks",
        "priority IN ('high', 'medium', 'low')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_personal_tasks_priority", "personal_tasks", type_="check")
    op.drop_column("personal_tasks", "priority")
