"""client_op_id idempotency keys for local workspace sync retries

本地工作区双向同步的幂等键（D-38）：同一 `client_op_id` 重复提交只产生一条记录，
避免同步重试/崩溃恢复时重复创建资料、记录、行动项、问题、音频。

Revision ID: 0027_client_op_id
Revises: 0026_ai_call_runtime
Create Date: 2026-11-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_client_op_id"
down_revision: str | None = "0026_ai_call_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "meeting_materials",
    "meeting_records",
    "action_items",
    "open_issues",
    "meeting_audio",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("client_op_id", sa.String(length=64), nullable=True))
        op.create_index(f"uq_{table}_client_op_id", table, ["client_op_id"], unique=True)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"uq_{table}_client_op_id", table_name=table)
        op.drop_column(table, "client_op_id")
