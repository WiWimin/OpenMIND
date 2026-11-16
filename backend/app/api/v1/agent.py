"""Agent API：会话、单轮对话（含 SSE）、确认门与运行查询。

特性开关 `AGENT_ENABLED=false` 时整个路由组返回 404，前端回退既有页面链路。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.agent import service as agent_service
from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.core.config import get_settings
from app.core.exceptions import AppError, error_body
from app.schemas.agent import (
    AgentMessageRead,
    AgentPendingActionDecision,
    AgentPendingActionRead,
    AgentRunRead,
    AgentRunStepRead,
    AgentSessionCreate,
    AgentSessionDeleteResult,
    AgentSessionRead,
    AgentSessionUpdate,
    AgentTurnRequest,
    AgentTurnResponse,
)
from app.schemas.common import Envelope, ListData

logger = logging.getLogger(__name__)


def _ensure_enabled() -> None:
    if not get_settings().agent_enabled:
        raise AppError(
            "RESOURCE_NOT_FOUND", "Agent 未启用", http_status=404, retryable=False
        )


router = APIRouter(tags=["agent"], dependencies=[Depends(_ensure_enabled)])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------- 会话


@router.get(
    "/agent/sessions", response_model=Envelope[ListData[AgentSessionRead]]
)
def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
    scene: str | None = None,
    meeting_id: str | None = None,
) -> Envelope[ListData[AgentSessionRead]]:
    items, total = agent_service.list_sessions(
        db,
        user_id=current_user.user_id,
        scene=scene,
        meeting_id=meeting_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items,
        AgentSessionRead,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.post("/agent/sessions/ensure", response_model=Envelope[AgentSessionRead])
def ensure_session(
    payload: AgentSessionCreate, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentSessionRead]:
    """按 `user + scene + meeting` 查找或创建默认会话（幂等，供前端挂载时恢复）。"""
    session = agent_service.ensure_session(
        db,
        user_id=current_user.user_id,
        session_id=None,
        scene=payload.scene.value,
        meeting_id=payload.meeting_id,
        title=payload.title,
    )
    return Envelope(data=AgentSessionRead.model_validate(session))


@router.post("/agent/sessions", response_model=Envelope[AgentSessionRead])
def create_session(
    payload: AgentSessionCreate, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentSessionRead]:
    session = agent_service.ensure_session(
        db,
        user_id=current_user.user_id,
        session_id=None,
        scene=payload.scene.value,
        meeting_id=payload.meeting_id,
        title=payload.title,
    )
    return Envelope(data=AgentSessionRead.model_validate(session))


@router.get("/agent/sessions/{session_id}", response_model=Envelope[AgentSessionRead])
def get_session(
    session_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentSessionRead]:
    session = agent_service.get_owned_session(db, session_id, current_user.user_id)
    return Envelope(data=AgentSessionRead.model_validate(session))


@router.patch("/agent/sessions/{session_id}", response_model=Envelope[AgentSessionRead])
def update_session(
    session_id: str,
    payload: AgentSessionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[AgentSessionRead]:
    session = agent_service.update_session(
        db,
        session_id=session_id,
        user_id=current_user.user_id,
        title=payload.title,
        status=payload.status.value if payload.status else None,
    )
    return Envelope(data=AgentSessionRead.model_validate(session))


@router.delete(
    "/agent/sessions/{session_id}", response_model=Envelope[AgentSessionDeleteResult]
)
def delete_session(
    session_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentSessionDeleteResult]:
    agent_service.delete_session(
        db, session_id=session_id, user_id=current_user.user_id
    )
    return Envelope(data=AgentSessionDeleteResult(session_id=session_id))


@router.get(
    "/agent/sessions/{session_id}/messages",
    response_model=Envelope[ListData[AgentMessageRead]],
)
def list_messages(
    session_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[AgentMessageRead]]:
    items, total = agent_service.list_messages(
        db,
        session_id=session_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items,
        AgentMessageRead,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get(
    "/agent/sessions/{session_id}/pending-actions",
    response_model=Envelope[list[AgentPendingActionRead]],
)
def list_pending_actions(
    session_id: str,
    db: DbSession,
    current_user: CurrentUser,
    status: str = "pending",
) -> Envelope[list[AgentPendingActionRead]]:
    actions = agent_service.list_pending_actions(
        db,
        session_id=session_id,
        user_id=current_user.user_id,
        status=status or None,
    )
    return Envelope(
        data=[AgentPendingActionRead.model_validate(item) for item in actions]
    )


# ---------------------------------------------------------------- 单轮


@router.post("/agent/turns", response_model=Envelope[AgentTurnResponse])
def create_turn(
    payload: AgentTurnRequest, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentTurnResponse]:
    result = agent_service.handle_turn(
        db, user_id=current_user.user_id, payload=payload
    )
    return Envelope(data=result)


@router.post("/agent/turns/stream")
async def stream_turn(
    payload: AgentTurnRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """SSE：`intent` → `meta` → `delta`* → `pending_action`/`run` → `done`。

    首个事件前的错误（归属/会话等）由 FastAPI 统一异常处理为 JSON 错误体；
    事件流开始后的错误以 `error` 事件返回，不截断已开始的连接。
    """
    if not get_settings().sse_chat_enabled:
        raise AppError(
            "RESOURCE_NOT_FOUND", "流式问答未启用", http_status=404, retryable=False
        )
    # 首帧前先完成会话/意图准备：这一步的错误仍能返回统一 JSON 错误体
    prep = await run_in_threadpool(
        agent_service.prepare_turn, db, user_id=current_user.user_id, payload=payload
    )
    stream = agent_service.stream_turn(
        db, user_id=current_user.user_id, payload=payload, prep=prep
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event, data in stream:
                if await request.is_disconnected():
                    return
                yield _sse(event, data)
        except AppError as exc:
            # 响应已开始（SSE）：不能改状态码，按契约发 error 事件由前端展示
            yield _sse(
                "error",
                error_body(exc.error_code, exc.message, exc.retryable, exc.details),
            )
        except Exception:  # noqa: BLE001 — 流内异常统一归一，避免连接被截断
            logger.exception("Agent SSE 异常 path=/agent/turns/stream")
            yield _sse(
                "error",
                error_body("INTERNAL_ERROR", "生成失败，请稍后重试", True),
            )
        finally:
            await stream.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------- 确认门


@router.post(
    "/agent/pending-actions/{action_id}/approve",
    response_model=Envelope[AgentTurnResponse],
)
def approve_pending_action(
    action_id: str,
    payload: AgentPendingActionDecision,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[AgentTurnResponse]:
    result = agent_service.approve_pending_action(
        db,
        action_id=action_id,
        user_id=current_user.user_id,
        note=payload.note,
    )
    return Envelope(data=result)


@router.post(
    "/agent/pending-actions/{action_id}/reject",
    response_model=Envelope[AgentTurnResponse],
)
def reject_pending_action(
    action_id: str,
    payload: AgentPendingActionDecision,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[AgentTurnResponse]:
    result = agent_service.reject_pending_action(
        db,
        action_id=action_id,
        user_id=current_user.user_id,
        note=payload.note,
    )
    return Envelope(data=result)


# ---------------------------------------------------------------- 运行


@router.get("/agent/runs/{run_id}", response_model=Envelope[AgentRunRead])
def get_run(
    run_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentRunRead]:
    run = agent_service.get_owned_run(db, run_id, current_user.user_id)
    return Envelope(data=AgentRunRead.model_validate(run))


@router.get(
    "/agent/runs/{run_id}/steps", response_model=Envelope[list[AgentRunStepRead]]
)
def list_run_steps(
    run_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[list[AgentRunStepRead]]:
    steps = agent_service.list_run_steps(db, run_id, current_user.user_id)
    return Envelope(data=[AgentRunStepRead.model_validate(step) for step in steps])


@router.post("/agent/runs/{run_id}/cancel", response_model=Envelope[AgentRunRead])
def cancel_run(
    run_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AgentRunRead]:
    run = agent_service.cancel_run(db, run_id, current_user.user_id)
    return Envelope(data=AgentRunRead.model_validate(run))
