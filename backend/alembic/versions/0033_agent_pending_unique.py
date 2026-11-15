"""agent_pending_actions partial unique index

同一工作流同一时刻只允许一条待确认动作：避免重复登记产生两张确认卡，
并给「批准/拒绝」的条件 UPDATE 幂等提供数据库层兜底。

存量先去重（同一 run 的重复 pending 保留最新一条，其余转 expired），
再建部分唯一索引 `run_id WHERE status = 'pending'`。

Revision ID: 0033_agent_pending_unique
Revises: 0032_agent_framework
Create Date: 2026-11-16

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_agent_pending_unique"
down_revision: str | None = "0032_agent_framework"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_agent_pending_actions_run_pending"
_WHERE = "run_id IS NOT NULL AND status = 'pending'"

# 同一 run 保留 created_at 最新的一条 pending，其余转 expired（不删除，保留可追溯）
_DEDUP = sa.text(
    """
    UPDATE agent_pending_actions a
    SET status = 'expired', decided_at = NOW()
    WHERE a.status = 'pending'
      AND a.run_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM agent_pending_actions b
        WHERE b.run_id = a.run_id
          AND b.status = 'pending'
          AND b.action_id <> a.action_id
          AND (b.created_at > a.created_at
               OR (b.created_at = a.created_at AND b.action_id > a.action_id))
      )
    """
)


def upgrade() -> None:
    op.execute(_DEDUP)
    op.create_index(
        _INDEX_NAME,
        "agent_pending_actions",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text(_WHERE),
        sqlite_where=sa.text(_WHERE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="agent_pending_actions")
