"""ai call logs runtime

`ai_call_logs` 升级为运行态审计（`ai-design.md 3.11`、`database.md 3.18`）：

- `job_id`：关联 `async_jobs.job_id`，打通任务与调用链路（不建 FK——审计为
  append-only，任务清理不应连坐日志）；
- `finished_at`：进入终态时间；`created_at` 即预创建/受理时间（`running` 时为空）；
- `fallback_scope`：降级来源标签（`none`/`global`；`user`/`scene`/`cross_provider`
  为后续演进预留值）；
- `meta`：纯标签扩展（重试/链路长度等），禁止提示词、用户原文与模型输出。

Revision ID: 0026_ai_call_runtime
Revises: 0025_ai_call_logs
Create Date: 2026-11-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_ai_call_runtime"
down_revision: str | None = "0025_ai_call_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_call_logs", sa.Column("job_id", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "ai_call_logs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_call_logs",
        sa.Column("fallback_scope", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "ai_call_logs",
        sa.Column(
            "meta",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_ai_call_logs_job_created",
        "ai_call_logs",
        ["job_id", "created_at"],
    )
    op.create_index(
        "ix_ai_call_logs_user_status",
        "ai_call_logs",
        ["user_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_call_logs_user_status", table_name="ai_call_logs")
    op.drop_index("ix_ai_call_logs_job_created", table_name="ai_call_logs")
    op.drop_column("ai_call_logs", "meta")
    op.drop_column("ai_call_logs", "fallback_scope")
    op.drop_column("ai_call_logs", "finished_at")
    op.drop_column("ai_call_logs", "job_id")
