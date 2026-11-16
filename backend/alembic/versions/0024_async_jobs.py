"""async jobs

Revision ID: 0024_async_jobs
Revises: 0023_parse_error_code
Create Date: 2026-11-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_async_jobs"
down_revision: str | None = "0023_parse_error_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "async_jobs",
        sa.Column("job_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_async_jobs_user_id", "async_jobs", ["user_id"])
    op.create_index("ix_async_jobs_resource_id", "async_jobs", ["resource_id"])
    op.create_index("ix_async_jobs_user_status", "async_jobs", ["user_id", "status"])
    op.create_index(
        "ix_async_jobs_resource", "async_jobs", ["resource_type", "resource_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_async_jobs_resource", table_name="async_jobs")
    op.drop_index("ix_async_jobs_user_status", table_name="async_jobs")
    op.drop_index("ix_async_jobs_resource_id", table_name="async_jobs")
    op.drop_index("ix_async_jobs_user_id", table_name="async_jobs")
    op.drop_table("async_jobs")
