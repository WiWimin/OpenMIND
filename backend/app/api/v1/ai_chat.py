from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import CurrentUser, DbSession
from app.core import metrics
from app.core.config import get_settings
from app.core.exceptions import AppError, error_body
from app.schemas.chat import (
    ChatFile,
    ChatRequest,
    ChatResponse,
    ChatSource,
    OrganizeRequest,
    OrganizeResponse,
)
from app.schemas.common import Envelope
from app.services import ai_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


def _sse(event: str, data: dict[str, Any]) -> str:
    """SSE 帧：`event:` + `data:`（JSON 不转义中文）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/meetings/{meeting_id}/chat", response_model=Envelope[ChatResponse])
def chat(
    meeting_id: str,
    payload: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[ChatResponse]:
    answer = ai_chat_service.chat(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        question=payload.question,
        context_scope=payload.context_scope.value,
        include_sources=payload.include_sources,
        model=payload.model,
        mode=payload.mode,
    )
    sources = (
        [
            ChatSource(
                meeting_id=source.meeting_id,
                material_id=source.material_id,
                record_id=source.record_id,
                excerpt=source.excerpt,
                document_id=source.document_id,
                document_name=source.document_name,
                origin=source.origin,
                url=source.url,
                title=source.title,
            )
            for source in answer.sources
        ]
        if payload.include_sources
        else []
    )
    return Envelope(
        data=ChatResponse(
            answer=answer.answer,
            sources=sources,
            insufficient_evidence=answer.insufficient_evidence,
            file=(
                ChatFile(filename=answer.file.filename, content=answer.file.content_md)
                if answer.file
                else None
            ),
        )
    )


@router.post("/meetings/{meeting_id}/chat/stream")
async def chat_stream(
    meeting_id: str,
    payload: ChatRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """SSE 流式问答（仅 `plan` 模式；**不使用统一信封**，见 `api.md` 5.7a）。

    首个增量前的错误（归属/检索/模型配置/首 token 失败）以普通 JSON
    错误体返回；首增量后的错误以 `event: error` 下发。
    """
    settings = get_settings()
    if not settings.sse_chat_enabled:
        raise AppError(
            "RESOURCE_NOT_FOUND", "流式问答未启用", http_status=404, retryable=False
        )
    if payload.mode == "build":
        raise AppError(
            "VALIDATION_ERROR",
            "Build 模式不支持流式，请使用同步问答接口",
            http_status=422,
        )
    # 同步准备：归属校验、检索、记忆、模型解析（DB 访问在返回流之前完成）
    session = ai_chat_service.prepare_chat(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        question=payload.question,
        context_scope=payload.context_scope.value,
        include_sources=payload.include_sources,
        model=payload.model,
    )
    sources = (
        [
            ChatSource(
                meeting_id=source.meeting_id,
                material_id=source.material_id,
                record_id=source.record_id,
                excerpt=source.excerpt,
                document_id=source.document_id,
                document_name=source.document_name,
                origin=source.origin,
                url=source.url,
                title=source.title,
            ).model_dump()
            for source in session.prepared.sources
        ]
        if payload.include_sources
        else []
    )
    usage: dict[str, int] = {}
    started = time.monotonic()
    stream = session.service.answer_stream(
        session.prepared, on_usage=lambda value: usage.update(value)
    )
    # 预取首增量：失败 → 普通 JSON 错误体（此时还没发响应头）
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:  # pragma: no cover — answer_stream 至少 yield 拒答
        first = None
    except AppError as exc:
        await stream.aclose()
        metrics.inc_counter("chat_stream_error_total")
        return JSONResponse(
            status_code=exc.http_status,
            content=error_body(exc.error_code, exc.message, exc.retryable, exc.details),
        )
    except Exception:  # noqa: BLE001
        await stream.aclose()
        logger.exception("流式问答首增量失败 meeting_id=%s", meeting_id)
        metrics.inc_counter("chat_stream_error_total")
        return JSONResponse(
            status_code=500, content=error_body("INTERNAL_ERROR", "未预期的服务端错误")
        )
    if first is None:
        await stream.aclose()
        metrics.inc_counter("chat_stream_error_total")
        return JSONResponse(
            status_code=502, content=error_body("MODEL_OUTPUT_INVALID", "模型输出为空")
        )

    heartbeat_s = settings.sse_heartbeat_seconds
    meta = {
        "insufficient_evidence": not session.prepared.has_evidence,
        "sources": sources,
        "model": session.model,
    }

    async def event_stream() -> AsyncIterator[str]:
        metrics.inc_counter("chat_stream_total")
        metrics.observe(
            "chat_stream_first_token_ms", (time.monotonic() - started) * 1000
        )
        # meta 在首增量取得后才下发，字节顺序保持 meta → delta
        yield _sse("meta", meta)
        answer_parts = [first]
        yield _sse("delta", {"text": first})
        pending: asyncio.Task[str] | None = None
        disconnected = False
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("流式问答客户端断开 meeting_id=%s", meeting_id)
                    disconnected = True
                    break
                if pending is None:
                    pending = asyncio.ensure_future(stream.__anext__())
                done, _ = await asyncio.wait(
                    {pending}, timeout=heartbeat_s if heartbeat_s > 0 else None
                )
                if not done:  # 空闲超时 → 注释心跳，保持连接
                    yield ": ping\n\n"
                    continue
                task, pending = pending, None
                try:
                    delta = task.result()
                except StopAsyncIteration:
                    break
                except AppError as exc:
                    metrics.inc_counter("chat_stream_error_total")
                    yield _sse(
                        "error",
                        {
                            "status": "error",
                            "error_code": exc.error_code,
                            "message": exc.message,
                            "retryable": exc.retryable,
                        },
                    )
                    return
                except Exception:  # noqa: BLE001
                    logger.exception("流式问答中途失败 meeting_id=%s", meeting_id)
                    metrics.inc_counter("chat_stream_error_total")
                    yield _sse(
                        "error",
                        {
                            "status": "error",
                            "error_code": "INTERNAL_ERROR",
                            "message": "未预期的服务端错误",
                            "retryable": True,
                        },
                    )
                    return
                answer_parts.append(delta)
                yield _sse("delta", {"text": delta})
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await stream.aclose()
        if disconnected:
            return  # 不写半条 assistant 消息
        yield _sse(
            "done",
            {
                "answer": "".join(answer_parts),
                "usage": usage or None,
                "latency_ms": int((time.monotonic() - started) * 1000),
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/meetings/{meeting_id}/organize", response_model=Envelope[OrganizeResponse])
def organize(
    meeting_id: str,
    payload: OrganizeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[OrganizeResponse]:
    outcome = ai_chat_service.organize(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        record_ids=payload.record_ids,
        style=payload.style,
        task=payload.task,
        text=payload.text,
        instruction=payload.instruction,
        audio_id=payload.audio_id,
        model=payload.model,
    )
    return Envelope(
        data=OrganizeResponse(
            task=outcome.task,
            organized_content=outcome.content,
            structured=outcome.structured,
            source_record_ids=outcome.source_record_ids,
        )
    )
