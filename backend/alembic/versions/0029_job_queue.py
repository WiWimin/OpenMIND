"""async job durable queue fields

Revision ID: 0029_job_queue
Revises: 0028_task_priority
Create Date: 2026-11-11

ADR-3 升级：async_jobs 增加认领/重试/心跳字段，支持独立 worker 的 DB 队列
（`FOR UPDATE SKIP LOCKED`），不引入 Redis/Celery。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_job_queue"
down_revision: str | None = "0028_task_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "async_jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "async_jobs",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "async_jobs", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "async_jobs", sa.Column("locked_by", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "async_jobs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "async_jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "async_jobs",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "async_jobs", sa.Column("payload", postgresql.JSONB(), nullable=True)
    )
    op.create_index(
        "ix_async_jobs_claim",
        "async_jobs",
        ["status", "next_run_at", "priority", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_async_jobs_claim", table_name="async_jobs")
    op.drop_column("async_jobs", "payload")
    op.drop_column("async_jobs", "priority")
    op.drop_column("async_jobs", "heartbeat_at")
    op.drop_column("async_jobs", "locked_at")
    op.drop_column("async_jobs", "locked_by")
    op.drop_column("async_jobs", "next_run_at")
    op.drop_column("async_jobs", "max_attempts")
    op.drop_column("async_jobs", "attempts")
