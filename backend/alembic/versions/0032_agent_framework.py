"""agent framework tables

Revision ID: 0032_agent_framework
Revises: 0031_rag_hnsw
Create Date: 2026-11-11

Agent 框架（不引入 LangGraph）：会话、消息、工作流实例、步骤轨迹与确认门。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_agent_framework"
down_revision: str | None = "0031_rag_hnsw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("meeting_id", sa.String(length=40), nullable=True),
        sa.Column("scene", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.meeting_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index("ix_agent_sessions_meeting_id", "agent_sessions", ["meeting_id"])
    op.create_index(
        "ix_agent_sessions_user_scene_meeting",
        "agent_sessions",
        ["user_id", "scene", "meeting_id", "updated_at"],
    )

    op.create_table(
        "agent_messages",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=True),
        sa.Column("structured", postgresql.JSONB(), nullable=True),
        sa.Column("sources", postgresql.JSONB(), nullable=True),
        sa.Column("file", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="completed"
        ),
        sa.Column("job_id", sa.String(length=40), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_agent_messages_session_created",
        "agent_messages",
        ["session_id", "created_at"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("meeting_id", sa.String(length=40), nullable=True),
        sa.Column("workflow", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.String(length=60), nullable=True),
        sa.Column("state", postgresql.JSONB(), nullable=True),
        sa.Column("job_id", sa.String(length=40), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_job_id", "agent_runs", ["job_id"])
    op.create_index(
        "ix_agent_runs_user_status", "agent_runs", ["user_id", "status", "created_at"]
    )

    op.create_table(
        "agent_run_steps",
        sa.Column("step_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("step_name", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"]),
        sa.PrimaryKeyConstraint("step_id"),
    )
    op.create_index(
        "ix_agent_run_steps_run_created", "agent_run_steps", ["run_id", "created_at"]
    )

    op.create_table(
        "agent_pending_actions",
        sa.Column("action_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index(
        "ix_agent_pending_actions_session_status",
        "agent_pending_actions",
        ["session_id", "status"],
    )
    op.create_index(
        "ix_agent_pending_actions_user_id", "agent_pending_actions", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_pending_actions_user_id", table_name="agent_pending_actions"
    )
    op.drop_index(
        "ix_agent_pending_actions_session_status", table_name="agent_pending_actions"
    )
    op.drop_table("agent_pending_actions")
    op.drop_index("ix_agent_run_steps_run_created", table_name="agent_run_steps")
    op.drop_table("agent_run_steps")
    op.drop_index("ix_agent_runs_user_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_job_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_messages_session_created", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index(
        "ix_agent_sessions_user_scene_meeting", table_name="agent_sessions"
    )
    op.drop_index("ix_agent_sessions_meeting_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
