from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.ai import audit
from app.ai.chat.trace import build_chat_trace
from app.ai.llm import LLMDelta
from app.ai.llm.reasoning import reasoning_capable
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
from app.services import ai_audit_service, ai_chat_service

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
    # 同步准备：归属校验、检索、记忆、模型解析（DB 访问在返回流之前完成）。
    # prepare_chat 是同步实现（DB + 同步 Embedding/Judge），必须放线程池，
    # 否则会阻塞事件循环、拖垮同进程的其他连接（含正在下发的 SSE 流）。
    session = await run_in_threadpool(
        ai_chat_service.prepare_chat,
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
        session.prepared,
        on_usage=lambda value: usage.update(value),
        thinking=payload.thinking,
    )
    # 审计预创建（running 行）：与同步问答同源，SSE 调用同样落 ai_call_logs。
    # 上下文必须在事件循环线程建立（流增量的 usage 才能记入事件）；
    # 写库放线程池，避免阻塞事件循环。
    handle = ai_audit_service.begin_call(
        user_id=current_user.user_id,
        scene="chat",
        model=session.model or "",
        provider=audit.provider_host(
            getattr(session.service.llm, "api_base", "") or ""
        ),
        transport="sse",
    )
    await run_in_threadpool(ai_audit_service.persist_start, db, handle)

    async def _finish_audit(status: str, error_code: str | None = None) -> None:
        """收尾（幂等）：结束上下文 + 独立会话写终态。"""
        ai_audit_service.close_context(handle)
        await run_in_threadpool(
            ai_audit_service.finish_in_fresh_session,
            handle,
            status=status,
            error_code=error_code,
        )

    # 预取首增量：失败 → 普通 JSON 错误体（此时还没发响应头）
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:  # pragma: no cover — answer_stream 至少 yield 拒答
        first = None
    except AppError as exc:
        await stream.aclose()
        metrics.inc_counter("chat_stream_error_total")
        await _finish_audit(ai_audit_service.STATUS_FAILED, exc.error_code)
        return JSONResponse(
            status_code=exc.http_status,
            content=error_body(exc.error_code, exc.message, exc.retryable, exc.details),
        )
    except Exception:  # noqa: BLE001
        await stream.aclose()
        logger.exception("流式问答首增量失败 meeting_id=%s", meeting_id)
        metrics.inc_counter("chat_stream_error_total")
        await _finish_audit(ai_audit_service.STATUS_FAILED, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=500, content=error_body("INTERNAL_ERROR", "未预期的服务端错误")
        )
    if first is None:
        await stream.aclose()
        metrics.inc_counter("chat_stream_error_total")
        await _finish_audit(ai_audit_service.STATUS_FAILED, "MODEL_OUTPUT_INVALID")
        return JSONResponse(
            status_code=502, content=error_body("MODEL_OUTPUT_INVALID", "模型输出为空")
        )

    heartbeat_s = settings.sse_heartbeat_seconds
    meta = {
        "insufficient_evidence": not session.prepared.has_evidence,
        "sources": sources,
        "model": session.model,
        # 真实执行步骤（理解 → 检索 → 生成）：供前端展示「推理链」，
        # 模型原生推理由 event: reasoning 单独下发
        "trace": build_chat_trace(
            intent="chat",
            scope=payload.context_scope.value,
            hits=len(session.prepared.sources),
            native=bool(
                payload.thinking
                and reasoning_capable(
                    session.model or "",
                    getattr(session.service.llm, "api_base", "") or "",
                )
            ),
        ),
    }

    async def event_stream() -> AsyncIterator[str]:
        # 审计终态初值：客户端断开 / GeneratorExit 都落 cancelled；
        # 正常完成与失败路径在退出前显式覆盖
        audit_status = ai_audit_service.STATUS_CANCELLED
        audit_error = ai_audit_service.ERROR_CLIENT_DISCONNECTED
        try:
            metrics.inc_counter("chat_stream_total")
            metrics.observe(
                "chat_stream_first_token_ms", (time.monotonic() - started) * 1000
            )
            # meta 在首增量取得后才下发，字节顺序保持 meta → reasoning/delta
            yield _sse("meta", meta)
            answer_parts: list[str] = []
            reasoning_parts: list[str] = []

            def _emit(chunk: LLMDelta) -> str:
                if chunk.kind == "reasoning":
                    reasoning_parts.append(chunk.text)
                    return _sse("reasoning", {"text": chunk.text})
                answer_parts.append(chunk.text)
                return _sse("delta", {"text": chunk.text})

            yield _emit(first)
            pending: asyncio.Task[LLMDelta] | None = None
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
                        chunk = task.result()
                    except StopAsyncIteration:
                        audit_status = ai_audit_service.STATUS_SUCCESS
                        audit_error = None
                        break
                    except AppError as exc:
                        audit_status = ai_audit_service.STATUS_FAILED
                        audit_error = exc.error_code
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
                        audit_status = ai_audit_service.STATUS_FAILED
                        audit_error = "INTERNAL_ERROR"
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
                    yield _emit(chunk)
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
                    "reasoning": "".join(reasoning_parts),
                    "reasoning_ms": int((time.monotonic() - started) * 1000),
                    "usage": usage or None,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                },
            )
        finally:
            # 审计收尾：成功 / 失败 / 断开三条路径统一在此落库（幂等）
            await _finish_audit(audit_status, audit_error)

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
