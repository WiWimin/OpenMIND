from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utc_now

_json_type = JSON().with_variant(postgresql.JSONB(), "postgresql")


class AgentSession(Base):
    """Agent 会话（按「页面场景 + 会议」隔离，服务端持久化）。"""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index(
            "ix_agent_sessions_user_scene_meeting",
            "user_id",
            "scene",
            "meeting_id",
            "updated_at",
        ),
    )

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), nullable=False, index=True
    )
    meeting_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("meetings.meeting_id"), nullable=True, index=True
    )
    scene: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    meta: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentMessage(Base):
    """Agent 消息：原文与 AI 结果分开存放，结构化结果只作展示候选。"""

    __tablename__ = "agent_messages"
    __table_args__ = (Index("ix_agent_messages_session_created", "session_id", "created_at"),)

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agent_sessions.session_id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # summary / polish / minutes / action_items / prepare / file / chat
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    structured: Mapped[dict | list | None] = mapped_column(_json_type, nullable=True)
    sources: Mapped[list | None] = mapped_column(_json_type, nullable=True)
    file: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    # streaming / completed / failed / cancelled
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", server_default="completed"
    )
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # 意图、置信度、耗时等运行元数据（用于评测与排障）
    meta: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class AgentRun(Base):
    """工作流实例：状态、当前步骤与 JSONB 状态快照（支持恢复）。"""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_user_status", "user_id", "status", "created_at"),)

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agent_sessions.session_id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), nullable=False, index=True
    )
    meeting_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    workflow: Mapped[str] = mapped_column(String(40), nullable=False)
    # pending / running / waiting / succeeded / failed / cancelled
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    current_step: Mapped[str | None] = mapped_column(String(60), nullable=True)
    state: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentRunStep(Base):
    """工作流步骤轨迹：输入/输出/重试/错误，便于审计与排障。"""

    __tablename__ = "agent_run_steps"
    __table_args__ = (Index("ix_agent_run_steps_run_created", "run_id", "created_at"),)

    step_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agent_runs.run_id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    input: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    output: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentPendingAction(Base):
    """确认门：需要用户明确批准后才执行的动作（联网检索等）。"""

    __tablename__ = "agent_pending_actions"
    __table_args__ = (
        Index("ix_agent_pending_actions_session_status", "session_id", "status"),
        # 同一工作流同一时刻只允许一条待确认动作：防重复登记产生两张确认卡。
        # 部分索引（SQLite 与 PostgreSQL 各自的 where 方言参数，测试跑内存库）
        Index(
            "uq_agent_pending_actions_run_pending",
            "run_id",
            unique=True,
            postgresql_where=text("run_id IS NOT NULL AND status = 'pending'"),
            sqlite_where=text("run_id IS NOT NULL AND status = 'pending'"),
        ),
    )

    action_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("agent_sessions.session_id"), nullable=False
    )
    run_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("agent_runs.run_id"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.user_id"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict | None] = mapped_column(_json_type, nullable=True)
    # pending / approved / rejected / expired
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
