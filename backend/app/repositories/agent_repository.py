from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentMessage,
    AgentPendingAction,
    AgentRun,
    AgentRunStep,
    AgentSession,
)

# ---------------------------------------------------------------- sessions


def create_session(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    meeting_id: str | None,
    scene: str,
    title: str | None = None,
    meta: dict | None = None,
) -> AgentSession:
    session = AgentSession(
        session_id=session_id,
        user_id=user_id,
        meeting_id=meeting_id,
        scene=scene,
        title=title,
        status="active",
        meta=meta,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> AgentSession | None:
    return db.execute(
        select(AgentSession).where(AgentSession.session_id == session_id)
    ).scalar_one_or_none()


def get_owned_session(
    db: Session, session_id: str, user_id: str
) -> AgentSession | None:
    return db.execute(
        select(AgentSession).where(
            AgentSession.session_id == session_id,
            AgentSession.user_id == user_id,
        )
    ).scalar_one_or_none()


def find_default_session(
    db: Session, *, user_id: str, scene: str, meeting_id: str | None
) -> AgentSession | None:
    statement = select(AgentSession).where(
        AgentSession.user_id == user_id,
        AgentSession.scene == scene,
        AgentSession.status == "active",
    )
    statement = (
        statement.where(AgentSession.meeting_id == meeting_id)
        if meeting_id is not None
        else statement.where(AgentSession.meeting_id.is_(None))
    )
    return db.execute(
        statement.order_by(AgentSession.updated_at.desc()).limit(1)
    ).scalar_one_or_none()


def list_sessions(
    db: Session,
    *,
    user_id: str,
    scene: str | None,
    meeting_id: str | None,
    limit: int,
    offset: int,
) -> list[AgentSession]:
    statement = select(AgentSession).where(AgentSession.user_id == user_id)
    if scene:
        statement = statement.where(AgentSession.scene == scene)
    if meeting_id is not None:
        statement = statement.where(AgentSession.meeting_id == meeting_id)
    return list(
        db.execute(
            statement.order_by(AgentSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


def count_sessions(
    db: Session, *, user_id: str, scene: str | None, meeting_id: str | None
) -> int:
    statement = select(AgentSession).where(AgentSession.user_id == user_id)
    if scene:
        statement = statement.where(AgentSession.scene == scene)
    if meeting_id is not None:
        statement = statement.where(AgentSession.meeting_id == meeting_id)
    return int(
        db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    )


def touch_session(
    db: Session, session: AgentSession, *, last_message_at: datetime | None = None
) -> None:
    if last_message_at is not None:
        session.last_message_at = last_message_at
    db.commit()
    db.refresh(session)


def update_session(db: Session, session: AgentSession, **values: object) -> AgentSession:
    for key, value in values.items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session: AgentSession) -> None:
    db.execute(
        delete(AgentPendingAction).where(
            AgentPendingAction.session_id == session.session_id
        )
    )
    db.execute(
        delete(AgentRunStep).where(
            AgentRunStep.run_id.in_(
                select(AgentRun.run_id).where(AgentRun.session_id == session.session_id)
            )
        )
    )
    db.execute(delete(AgentRun).where(AgentRun.session_id == session.session_id))
    db.execute(
        delete(AgentMessage).where(AgentMessage.session_id == session.session_id)
    )
    db.delete(session)
    db.commit()


# ---------------------------------------------------------------- messages


def create_message(
    db: Session,
    *,
    message_id: str,
    session_id: str,
    role: str,
    content: str,
    kind: str | None = None,
    structured: dict | list | None = None,
    sources: list | None = None,
    file: dict | None = None,
    status: str = "completed",
    job_id: str | None = None,
    meta: dict | None = None,
) -> AgentMessage:
    message = AgentMessage(
        message_id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        kind=kind,
        structured=structured,
        sources=sources,
        file=file,
        status=status,
        job_id=job_id,
        meta=meta,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def update_message(db: Session, message: AgentMessage, **values: object) -> AgentMessage:
    for key, value in values.items():
        setattr(message, key, value)
    db.commit()
    db.refresh(message)
    return message


def list_messages(
    db: Session, *, session_id: str, limit: int, offset: int
) -> list[AgentMessage]:
    return list(
        db.execute(
            select(AgentMessage)
            .where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.asc(), AgentMessage.message_id.asc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


def count_messages(db: Session, *, session_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(AgentMessage)
            .where(AgentMessage.session_id == session_id)
        ).scalar_one()
    )


# ---------------------------------------------------------------- runs


def create_run(
    db: Session,
    *,
    run_id: str,
    session_id: str,
    user_id: str,
    meeting_id: str | None,
    workflow: str,
    state: dict | None = None,
) -> AgentRun:
    run = AgentRun(
        run_id=run_id,
        session_id=session_id,
        user_id=user_id,
        meeting_id=meeting_id,
        workflow=workflow,
        status="pending",
        state=state or {},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_owned_run(db: Session, run_id: str, user_id: str) -> AgentRun | None:
    return db.execute(
        select(AgentRun).where(AgentRun.run_id == run_id, AgentRun.user_id == user_id)
    ).scalar_one_or_none()


def find_active_run(
    db: Session, *, session_id: str, workflow: str, resource_id: str
) -> AgentRun | None:
    """幂等：同一会话、同一工作流、同一资源只允许一个进行中的 run。"""
    statement = (
        select(AgentRun)
        .where(
            AgentRun.session_id == session_id,
            AgentRun.workflow == workflow,
            AgentRun.status.in_(("pending", "running", "waiting")),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    for run in db.execute(statement).scalars().all():
        if (run.state or {}).get("resource_id") == resource_id:
            return run
    return None


def update_run(db: Session, run: AgentRun, **values: object) -> AgentRun:
    for key, value in values.items():
        setattr(run, key, value)
    db.commit()
    db.refresh(run)
    return run


def list_runs(
    db: Session, *, user_id: str, limit: int, offset: int
) -> list[AgentRun]:
    return list(
        db.execute(
            select(AgentRun)
            .where(AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------- steps


def create_step(
    db: Session,
    *,
    step_id: str,
    run_id: str,
    step_name: str,
    status: str,
    attempt: int,
    input: dict | None = None,
    output: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    finished_at: datetime | None = None,
) -> AgentRunStep:
    step = AgentRunStep(
        step_id=step_id,
        run_id=run_id,
        step_name=step_name,
        status=status,
        attempt=attempt,
        input=input,
        output=output,
        error_code=error_code,
        error_message=error_message,
        finished_at=finished_at,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def list_steps(db: Session, *, run_id: str) -> list[AgentRunStep]:
    return list(
        db.execute(
            select(AgentRunStep)
            .where(AgentRunStep.run_id == run_id)
            .order_by(AgentRunStep.created_at.asc(), AgentRunStep.step_id.asc())
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------- pending actions


def create_pending_action(
    db: Session,
    *,
    action_id: str,
    session_id: str,
    run_id: str | None,
    user_id: str,
    action_type: str,
    question: str,
    payload: dict | None,
    expires_at: datetime | None,
) -> AgentPendingAction:
    action = AgentPendingAction(
        action_id=action_id,
        session_id=session_id,
        run_id=run_id,
        user_id=user_id,
        action_type=action_type,
        question=question,
        payload=payload,
        status="pending",
        expires_at=expires_at,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def get_owned_pending_action(
    db: Session, action_id: str, user_id: str
) -> AgentPendingAction | None:
    return db.execute(
        select(AgentPendingAction).where(
            AgentPendingAction.action_id == action_id,
            AgentPendingAction.user_id == user_id,
        )
    ).scalar_one_or_none()


def find_pending_action(
    db: Session, *, session_id: str, action_type: str
) -> AgentPendingAction | None:
    return db.execute(
        select(AgentPendingAction)
        .where(
            AgentPendingAction.session_id == session_id,
            AgentPendingAction.action_type == action_type,
            AgentPendingAction.status == "pending",
        )
        .order_by(AgentPendingAction.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def claim_pending_action(
    db: Session,
    *,
    action_id: str,
    user_id: str,
    status: str,
    now: datetime,
) -> AgentPendingAction | None:
    """把 pending 状态的确认门原子地改成终态（批准/拒绝/过期）。

    用单条条件 UPDATE 完成「检查 + 置位」，避免先读后写的并发窗口：
    只有 `status='pending'` 且未过期的行会被更新，`rowcount != 1` 即已被
    其他请求处理。返回 None 时由调用方重读以区分 404 / 409。
    """
    statement = (
        update(AgentPendingAction)
        .where(
            AgentPendingAction.action_id == action_id,
            AgentPendingAction.user_id == user_id,
            AgentPendingAction.status == "pending",
            or_(
                AgentPendingAction.expires_at.is_(None),
                AgentPendingAction.expires_at > now,
            ),
        )
        .values(status=status, decided_at=now)
    )
    result = db.execute(statement)
    db.commit()
    if result.rowcount != 1:
        return None
    return get_owned_pending_action(db, action_id, user_id)


def update_pending_action(
    db: Session, action: AgentPendingAction, **values: object
) -> AgentPendingAction:
    for key, value in values.items():
        setattr(action, key, value)
    db.commit()
    db.refresh(action)
    return action


def list_pending_actions(
    db: Session, *, session_id: str, status: str | None = "pending"
) -> list[AgentPendingAction]:
    statement = select(AgentPendingAction).where(
        AgentPendingAction.session_id == session_id
    )
    if status:
        statement = statement.where(AgentPendingAction.status == status)
    return list(
        db.execute(statement.order_by(AgentPendingAction.created_at.desc()))
        .scalars()
        .all()
    )


def delete_by_user(db: Session, user_id: str) -> None:
    """账号注销时清理 Agent 数据（与其它用户数据一致）。"""
    session_ids = select(AgentSession.session_id).where(AgentSession.user_id == user_id)
    db.execute(delete(AgentPendingAction).where(AgentPendingAction.user_id == user_id))
    db.execute(
        delete(AgentRunStep).where(
            AgentRunStep.run_id.in_(select(AgentRun.run_id).where(AgentRun.user_id == user_id))
        )
    )
    db.execute(delete(AgentRun).where(AgentRun.user_id == user_id))
    db.execute(delete(AgentMessage).where(AgentMessage.session_id.in_(session_ids)))
    db.execute(delete(AgentSession).where(AgentSession.user_id == user_id))