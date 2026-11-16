"""ai call logs

Revision ID: 0025_ai_call_logs
Revises: 0024_async_jobs
Create Date: 2026-11-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_ai_call_logs"
down_revision: str | None = "0024_async_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_call_logs",
        sa.Column("log_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("scene", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=200), nullable=False),
        sa.Column(
            "transport", sa.String(length=10), nullable=False, server_default="sync"
        ),
        sa.Column(
            "status", sa.String(length=10), nullable=False, server_default="success"
        ),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback_from", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index("ix_ai_call_logs_user_id", "ai_call_logs", ["user_id"])
    op.create_index(
        "ix_ai_call_logs_user_created", "ai_call_logs", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_ai_call_logs_scene_created", "ai_call_logs", ["scene", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_call_logs_scene_created", table_name="ai_call_logs")
    op.drop_index("ix_ai_call_logs_user_created", table_name="ai_call_logs")
    op.drop_index("ix_ai_call_logs_user_id", table_name="ai_call_logs")
    op.drop_table("ai_call_logs")
