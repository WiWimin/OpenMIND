"""Agent 编排服务：会话持久化、单轮路由、工作流执行与确认门。

依赖方向：`api → agent → services → ai`。本模块只做编排，不直接写业务表；
纪要/行动项/准备稿等仍由既有 service 创建，且保持「候选 → 用户确认」边界。
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.agent.intent import classify
from app.agent.tools import AgentContext, tool_functions
from app.agent.workflow import WorkflowResult, WorkflowRunner
from app.agent.workflows import get_workflow
from app.ai.chat import ChatAnswer
from app.ai.chat.trace import build_chat_trace
from app.ai.llm.reasoning import reasoning_capable
from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.agent import AgentMessage, AgentPendingAction, AgentRun, AgentSession
from app.repositories import (
    agent_repository,
    material_repository,
    minutes_repository,
    record_repository,
)
from app.schemas.action_item import ActionItemRead
from app.schemas.agent import (
    AgentIntent,
    AgentIntentDecision,
    AgentMessageRead,
    AgentPendingActionRead,
    AgentReply,
    AgentRunRead,
    AgentTurnOptions,
    AgentTurnRequest,
    AgentTurnResponse,
)
from app.schemas.chat import ChatFile, ChatSource, OrganizeTask
from app.schemas.minutes import MinutesGenerateRequest, MinutesTemplate
from app.schemas.preparation import PreparationRead
from app.services import (
    action_item_service,
    ai_chat_service,
    audio_service,
    brief_service,
    issue_service,
    job_service,
    job_tasks,
    meeting_service,
    minutes_service,
    preparation_service,
)
from app.utils.ids import new_id

logger = logging.getLogger(__name__)

_CHAT_INTENTS = {
    AgentIntent.chat,
    AgentIntent.knowledge_search,
    AgentIntent.build_file,
    AgentIntent.web_search,
}
_HELP_TEXT = (
    "我可以帮你：\n"
    "- 基于会议资料/记录回答问题并标注来源；\n"
    "- 生成会前准备稿、整理记录、生成纪要草稿；\n"
    "- 提取行动项与未解决问题（均为待确认草稿）；\n"
    "- 资料不足时，先征求你的同意再联网检索。"
)


# ---------------------------------------------------------------- 会话


def ensure_session(
    db: Session,
    *,
    user_id: str,
    session_id: str | None,
    scene: str,
    meeting_id: str | None,
    title: str | None = None,
) -> AgentSession:
    if session_id:
        session = agent_repository.get_owned_session(db, session_id, user_id)
        if session is None:
            raise resource_not_found("会话")
        if meeting_id and session.meeting_id and session.meeting_id != meeting_id:
            raise AppError(
                "VALIDATION_ERROR", "会话与会议不匹配", http_status=422
            )
        return session

    if meeting_id:
        meeting_service.get_owned_meeting(db, meeting_id, user_id)

    existing = agent_repository.find_default_session(
        db, user_id=user_id, scene=scene, meeting_id=meeting_id
    )
    if existing is not None:
        return existing
    return agent_repository.create_session(
        db,
        session_id=new_id("ags"),
        user_id=user_id,
        meeting_id=meeting_id,
        scene=scene,
        title=title,
        meta={"migrated": False},
    )


def list_sessions(
    db: Session,
    *,
    user_id: str,
    scene: str | None,
    meeting_id: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AgentSession], int]:
    offset = (page - 1) * page_size
    items = agent_repository.list_sessions(
        db,
        user_id=user_id,
        scene=scene,
        meeting_id=meeting_id,
        limit=page_size,
        offset=offset,
    )
    total = agent_repository.count_sessions(
        db, user_id=user_id, scene=scene, meeting_id=meeting_id
    )
    return items, total


def get_owned_session(db: Session, session_id: str, user_id: str) -> AgentSession:
    session = agent_repository.get_owned_session(db, session_id, user_id)
    if session is None:
        raise resource_not_found("会话")
    return session


def list_messages(
    db: Session, *, session_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[AgentMessage], int]:
    get_owned_session(db, session_id, user_id)
    offset = (page - 1) * page_size
    items = agent_repository.list_messages(
        db, session_id=session_id, limit=page_size, offset=offset
    )
    total = agent_repository.count_messages(db, session_id=session_id)
    return items, total


def update_session(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    title: str | None = None,
    status: str | None = None,
) -> AgentSession:
    session = get_owned_session(db, session_id, user_id)
    values: dict[str, Any] = {}
    if title is not None:
        values["title"] = title
    if status is not None:
        values["status"] = status
    return agent_repository.update_session(db, session, **values)


def delete_session(db: Session, *, session_id: str, user_id: str) -> None:
    session = get_owned_session(db, session_id, user_id)
    agent_repository.delete_session(db, session)


# ---------------------------------------------------------------- 单轮


@dataclass
class _TurnPrep:
    session: AgentSession
    user_message: AgentMessage
    decision: AgentIntentDecision
    # 本会话此前的对话历史（不含当前这一轮），供问答类意图注入 prompt
    history: list[dict[str, str]] = field(default_factory=list)


@dataclass
class _DispatchOutcome:
    reply: AgentReply | None = None
    pending: AgentPendingAction | None = None
    run: AgentRun | None = None
    accepted: bool = False
    # 已由工作流落库的助手消息（避免调用方重复写入）
    message: AgentMessage | None = None


def _meeting_state(db: Session, meeting_id: str | None) -> str:
    if not meeting_id:
        return ""
    try:
        materials = material_repository.count_by_meeting(db, meeting_id)
        records = record_repository.count_by_meeting(db, meeting_id)
        minutes = minutes_repository.count_by_meeting(db, meeting_id)
    except Exception:  # noqa: BLE001 — 状态摘要失败不影响路由
        return ""
    return f"资料 {materials} 份，记录 {records} 条，纪要 {minutes} 份"


def prepare_turn(db: Session, *, user_id: str, payload: AgentTurnRequest) -> _TurnPrep:
    """单轮前置：确保会话、落用户消息、产出意图决策。

    在 SSE 首帧之前调用（`api/v1/agent.py`），使归属/会话类错误仍能返回
    统一 JSON 错误体，而不是把已开始的流截断。
    """
    session = ensure_session(
        db,
        user_id=user_id,
        session_id=payload.session_id,
        scene=payload.scene.value,
        meeting_id=payload.meeting_id,
    )
    user_message = agent_repository.create_message(
        db,
        message_id=new_id("agm"),
        session_id=session.session_id,
        role="user",
        content=payload.message,
        status="completed",
    )
    decision = classify(
        db,
        user_id=user_id,
        message=payload.message,
        scene=payload.scene.value,
        meeting_state=_meeting_state(db, session.meeting_id),
        explicit=payload.intent,
    )
    agent_repository.update_message(
        db, user_message, meta={"intent": decision.intent.value, "confidence": decision.confidence}
    )
    agent_repository.touch_session(
        db, session, last_message_at=user_message.created_at
    )
    # 关闭多轮上下文时不做历史查询（问答链路仍会按 include_history 过滤）
    history = (
        ai_chat_service.load_history(
            db,
            session.session_id,
            exclude_message_id=user_message.message_id,
        )
        if payload.options.include_history
        else []
    )
    return _TurnPrep(
        session=session,
        user_message=user_message,
        decision=decision,
        history=history,
    )


def _to_chat_sources(sources: list[Any]) -> list[ChatSource]:
    result: list[ChatSource] = []
    for source in sources:
        if isinstance(source, ChatSource):
            result.append(source)
        elif isinstance(source, dict):
            result.append(ChatSource.model_validate(source))
        else:
            result.append(ChatSource.model_validate(source.__dict__))
    return result


def _reply_from_chat_answer(answer: ChatAnswer) -> AgentReply:
    return AgentReply(
        content=answer.answer,
        sources=_to_chat_sources(answer.sources),
        note=(
            "证据不足，回答仅供参考。"
            if answer.insufficient_evidence
            and not any(source.origin == "web" for source in _to_chat_sources(answer.sources))
            else None
        ),
        file=(
            ChatFile(filename=answer.file.filename, content=answer.file.content_md)
            if answer.file
            else None
        ),
    )


def _infer_template(message: str) -> MinutesTemplate | None:
    if any(word in message for word in ("精简", "简洁")):
        return MinutesTemplate.concise
    if any(word in message for word in ("任务清单", "待办", "行动项")):
        return MinutesTemplate.task_list
    if any(word in message for word in ("正式", "标准", "完整")):
        return MinutesTemplate.standard
    return None


def _create_pending(
    db: Session,
    *,
    session: AgentSession,
    user_id: str,
    action_type: str,
    question: str,
    payload: dict | None = None,
    run: AgentRun | None = None,
) -> AgentPendingAction:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=max(1, settings.agent_pending_action_ttl_minutes)
    )
    return agent_repository.create_pending_action(
        db,
        action_id=new_id("aga"),
        session_id=session.session_id,
        run_id=run.run_id if run else None,
        user_id=user_id,
        action_type=action_type,
        question=question,
        payload=payload,
        expires_at=expires_at,
    )


def _budgeted_workflow(name: str):
    """按配置覆盖工作流预算（AGENT_MAX_STEPS / AGENT_MAX_WALL_SECONDS）。"""
    settings = get_settings()
    return replace(
        get_workflow(name),
        max_steps=max(1, settings.agent_max_steps),
        max_wall_s=max(1.0, settings.agent_max_wall_seconds),
    )


def _run_workflow(
    db: Session, *, run: AgentRun, context: AgentContext
) -> tuple[WorkflowResult, AgentMessage | None]:
    recorder = _DbStepRecorder(db, run.run_id)

    def _cancelled() -> bool:
        try:
            db.refresh(run)
        except Exception:  # noqa: BLE001
            return False
        return run.status == "cancelled"

    runner = WorkflowRunner(
        tool_functions(), recorder=recorder, should_cancel=_cancelled
    )
    # 预算来自配置，不再用引擎默认值（见 _budgeted_workflow）
    workflow = _budgeted_workflow(run.workflow)
    result = runner.run(workflow, state=dict(run.state or {}), context=context)
    message = _persist_run_outcome(db, run=run, result=result, context=context)
    return result, message


def _persist_run_outcome(
    db: Session,
    *,
    run: AgentRun,
    result: WorkflowResult,
    context: AgentContext,
) -> AgentMessage | None:
    now = datetime.now(UTC)
    if result.status == "waiting" and result.pending_action is not None:
        pending = result.pending_action
        action = _create_pending(
            db,
            session=get_owned_session(db, run.session_id, run.user_id),
            user_id=run.user_id,
            action_type=pending.action_type,
            question=pending.question,
            payload=pending.payload,
            run=run,
        )
        message = agent_repository.create_message(
            db,
            message_id=new_id("agm"),
            session_id=run.session_id,
            role="assistant",
            content=pending.question,
            status="completed",
            meta={"pending_action_id": action.action_id},
        )
        agent_repository.update_run(
            db,
            run,
            status="waiting",
            current_step=result.current_step,
            state=dict(result.state),
        )
        return message

    if result.status == "succeeded":
        state = result.state
        content = str(state.get("answer") or state.get("content") or "已完成。")
        kind = state.get("kind")
        sources = state.get("sources") or []
        message = agent_repository.create_message(
            db,
            message_id=new_id("agm"),
            session_id=run.session_id,
            role="assistant",
            content=content,
            kind=str(kind) if kind else None,
            sources=sources or None,
            status="completed",
            meta={"workflow": run.workflow, "run_id": run.run_id},
        )
        agent_repository.update_run(
            db,
            run,
            status="succeeded",
            current_step=result.current_step,
            state=dict(state),
            finished_at=now,
        )
        return message

    if result.status == "cancelled":
        agent_repository.update_run(
            db, run, status="cancelled", finished_at=now, state=dict(result.state)
        )
        return None

    agent_repository.update_run(
        db,
        run,
        status="failed",
        current_step=result.current_step,
        state=dict(result.state),
        error_code=result.error_code,
        error_message=result.error_message,
        finished_at=now,
    )
    # 失败以 run 为唯一事实来源：不再落 failed 消息，
    # 由调用方抛 502（同步）/ 发 error 事件（SSE），避免用户看到两次错误
    return None


def _dispatch(
    db: Session,
    *,
    user_id: str,
    session: AgentSession,
    decision: AgentIntentDecision,
    message: str,
    options: AgentTurnOptions,
    history: list[dict[str, str]] | None = None,
) -> _DispatchOutcome:
    intent = decision.intent
    settings = get_settings()

    # 简单文本任务（润色/精简/改写/翻译）：单次 LLM，无检索/无落库/无确认门。
    # 显式快捷任务优先于意图路由，避免同一句话被其他规则抢占。
    if options.quick_task:
        text = (message or "").strip()
        if not text:
            raise AppError("VALIDATION_ERROR", "请先输入需要处理的文本", http_status=422)
        content = ai_chat_service.quick_task(
            db,
            user_id=user_id,
            text=text,
            task=options.quick_task,
            instruction=options.context or "",
            model=options.model,
        )
        return _DispatchOutcome(
            reply=AgentReply(
                content=content,
                note="仅调整表达方式，不会覆盖原始记录。",
            )
        )

    if intent in (AgentIntent.clarify, AgentIntent.help):
        content = (
            decision.clarification_question
            if intent is AgentIntent.clarify
            else _HELP_TEXT
        )
        return _DispatchOutcome(reply=AgentReply(content=content or _HELP_TEXT))

    if intent is AgentIntent.transcribe:
        return _DispatchOutcome(
            reply=AgentReply(
                content="转写在「录音转写」页面完成：上传或实时录音后校对文本并确认，系统会自动生成纪要草稿。",
                note="也可以直接把转写文本粘贴到对话里，让我整理。",
            )
        )

    if intent in (AgentIntent.chat, AgentIntent.knowledge_search, AgentIntent.build_file):
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        scope = (
            "knowledge_base"
            if intent is AgentIntent.knowledge_search
            else options.context_scope
        )
        answer = ai_chat_service.chat(
            db,
            meeting_id=session.meeting_id,
            user_id=user_id,
            question=message,
            context_scope=scope,
            include_sources=options.include_sources,
            model=options.model,
            mode="build" if intent is AgentIntent.build_file else options.mode,
            allow_web=not (
                settings.web_search_enabled
                and settings.web_search_require_confirmation
            ),
            history=list(history or []) if options.include_history else [],
        )
        if (
            answer.insufficient_evidence
            and settings.web_search_enabled
            and settings.web_search_require_confirmation
        ):
            pending = _create_pending(
                db,
                session=session,
                user_id=user_id,
                action_type="web_search",
                question=f"会议资料中没有找到「{message}」的相关证据，是否联网检索后再回答？",
                payload={
                    "question": message,
                    "options": options.model_dump(mode="json"),
                },
            )
            return _DispatchOutcome(
                reply=AgentReply(
                    content="会议资料中没有找到相关证据。",
                    note="是否联网检索后再回答？",
                ),
                pending=pending,
            )
        return _DispatchOutcome(reply=_reply_from_chat_answer(answer))

    if intent is AgentIntent.web_search:
        run, message_row = _start_web_fallback(
            db,
            user_id=user_id,
            session=session,
            question=message,
            options=options,
            require_confirmation=settings.web_search_require_confirmation,
        )
        return _outcome_from_run(db, run=run, session=session, message=message_row)

    if intent is AgentIntent.brief:
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        brief_outcome = brief_service.generate_brief(
            db,
            meeting_id=session.meeting_id,
            user_id=user_id,
            user_goal=options.user_goal or message or None,
            model=options.model,
        )
        if brief_outcome.empty:
            return _DispatchOutcome(
                reply=AgentReply(
                    content="本场会议还没有可用资料，无法生成会前速览。",
                    note="请先上传会议资料，或直接告诉我想重点了解哪方面。",
                )
            )
        return _DispatchOutcome(
            reply=AgentReply(
                content=brief_service.render_brief_text(brief_outcome),
                kind="brief",
                structured=brief_outcome.brief.model_dump(mode="json"),
                sources=brief_outcome.sources,
                note=f"基于本场 {brief_outcome.material_count} 份资料生成，仅供会前速读。",
            )
        )

    if intent is AgentIntent.prepare:
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        preparation = preparation_service.generate_preparation(
            db,
            meeting_id=session.meeting_id,
            user_id=user_id,
            user_goal=message or options.user_goal,
            include_history=options.include_history,
            model=options.model,
            template_id=options.template_id,
        )
        checklist = preparation.checklist
        preview = "\n".join(f"- {item}" for item in checklist[:3]) or "- 暂无准备清单"
        content = (
            f"已生成会前准备草稿，共 {len(checklist)} 项准备清单：\n\n{preview}"
        )
        if len(checklist) > 3:
            content += f"\n\n> 另有 {len(checklist) - 3} 项，请在左侧确认并查看完整清单。"
        else:
            content += "\n\n> 完整准备稿请在左侧确认查看。"
        return _DispatchOutcome(
            reply=AgentReply(
                content=content,
                note=(
                    "准备稿已确认。"
                    if preparation.status == "confirmed"
                    else "草稿已生成，确认后会作为会中与纪要阶段的上下文。"
                ),
                result=PreparationRead.model_validate(preparation).model_dump(mode="json"),
            )
        )

    if intent is AgentIntent.minutes_generate:
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        wants_actions = options.include_action_items or any(
            word in message for word in ("待办", "行动项", "任务")
        )
        minutes = minutes_service.generate_minutes(
            db,
            meeting_id=session.meeting_id,
            user_id=user_id,
            payload=MinutesGenerateRequest(
                record_ids=[],
                include_action_items=wants_actions,
                include_materials=options.include_materials,
                template=_infer_template(message),
                template_id=options.template_id,
            ),
        )
        meeting = meeting_service.get_owned_meeting(db, session.meeting_id, user_id)
        # 正文只给「一句话介绍」，纪要全文放进 file（前端渲染文件卡 + 右侧查看/编辑）
        meta = {
            "minutes_id": minutes.minutes_id,
            "version": minutes.version,
            "status": minutes.status,
            "template": minutes.template,
            "title": meeting.title or "",
        }
        return _DispatchOutcome(
            reply=AgentReply(
                content=(
                    f"已生成《{meeting.title or '会议纪要'}》纪要草稿 v{minutes.version}，"
                    f"状态「{minutes.status}」。全文见下方文件卡，点击可在右侧查看与编辑，"
                    "确认后才会作为任务与检索的依据。"
                ),
                kind="minutes",
                file=ChatFile(
                    filename=f"{meeting.title or '会议'}-纪要-v{minutes.version}.md",
                    content=minutes.content,
                ),
                structured=meta,
                result=meta,
            )
        )

    if intent is AgentIntent.organize:
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        outcome = ai_chat_service.organize(
            db,
            meeting_id=session.meeting_id,
            user_id=user_id,
            record_ids=[],
            style="",
            task=OrganizeTask.organize,
            instruction=message,
            model=options.model,
        )
        return _DispatchOutcome(
            reply=AgentReply(
                content=outcome.content,
                note="整理稿仅作展示，不会覆盖原始记录。",
                result={"organized_content": outcome.content},
            )
        )

    if intent is AgentIntent.action_items_extract:
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        items = action_item_service.extract_action_items(
            db, meeting_id=session.meeting_id, user_id=user_id, record_ids=[]
        )
        if not items:
            return _DispatchOutcome(
                reply=AgentReply(
                    content="当前会议记录中没有检测到明确的行动项。",
                    note="可以补充或整理会议记录后重试。",
                )
            )
        payload = [
            ActionItemRead.model_validate(item).model_dump(mode="json") for item in items
        ]
        return _DispatchOutcome(
            reply=AgentReply(
                content=(
                    f"已提取 {len(items)} 条行动项候选，并保存为待确认草稿。"
                    "打开下方清单可逐条确认，确认后可转为个人任务。"
                ),
                kind="action_items",
                structured=payload,
                result=payload,
            )
        )

    if intent is AgentIntent.issues_extract:
        if not session.meeting_id:
            raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
        issues = issue_service.extract_issues(
            db, meeting_id=session.meeting_id, user_id=user_id, record_ids=[]
        )
        if not issues:
            return _DispatchOutcome(
                reply=AgentReply(content="当前会议记录中没有检测到未解决问题。")
            )
        lines = "\n".join(f"- {issue.description}" for issue in issues)
        return _DispatchOutcome(
            reply=AgentReply(
                content=f"## 提取到 {len(issues)} 个未解决问题\n\n{lines}",
                note="已保存为问题草稿，可在「问题」区域跟进。",
            )
        )

    return _DispatchOutcome(reply=AgentReply(content=_HELP_TEXT))


def _start_web_fallback(
    db: Session,
    *,
    user_id: str,
    session: AgentSession,
    question: str,
    options: AgentTurnOptions,
    require_confirmation: bool,
) -> tuple[AgentRun, AgentMessage | None]:
    run = agent_repository.create_run(
        db,
        run_id=new_id("agr"),
        session_id=session.session_id,
        user_id=user_id,
        meeting_id=session.meeting_id,
        workflow="web_fallback",
        state={
            "question": question,
            "require_confirmation": require_confirmation,
            "options": options.model_dump(mode="json"),
            "session_id": session.session_id,
            "meeting_id": session.meeting_id,
            "scene": session.scene,
        },
    )
    context = AgentContext(
        db=db,
        user_id=user_id,
        session_id=session.session_id,
        meeting_id=session.meeting_id,
        scene=session.scene,
        options=options,
        question=question,
    )
    agent_repository.update_run(
        db, run, status="running", started_at=datetime.now(UTC)
    )
    _, message = _run_workflow(db, run=run, context=context)
    db.refresh(run)
    return run, message


def _raise_if_run_failed(run: AgentRun) -> None:
    """工作流失败 → 统一抛 502。

    失败以 `agent_runs` 为唯一事实来源（不落 failed 消息），同步路径靠抛错、
    SSE 路径靠 error 事件告知前端，避免同一次失败被渲染两遍。
    """
    if run.status != "failed":
        return
    raise AppError(
        run.error_code or "INTERNAL_ERROR",
        run.error_message or "Agent 工作流执行失败",
        http_status=502,
        retryable=True,
    )


def _outcome_from_run(
    db: Session,
    *,
    run: AgentRun,
    session: AgentSession,
    message: AgentMessage | None,
) -> _DispatchOutcome:
    state = dict(run.state or {})
    if run.status == "waiting":
        pending = agent_repository.find_pending_action(
            db, session_id=session.session_id, action_type="web_search"
        )
        return _DispatchOutcome(
            reply=AgentReply(
                content="会议资料中没有找到相关证据。",
                note="是否联网检索后再回答？",
            ),
            pending=pending,
            run=run,
            message=message,
        )
    if run.status == "failed":
        _raise_if_run_failed(run)
    return _DispatchOutcome(
        reply=AgentReply(
            content=str(state.get("answer") or "已完成。"),
            sources=_to_chat_sources(state.get("sources") or []),
            note=(
                "以上回答基于联网检索，仅供参考。"
                if state.get("sources")
                else None
            ),
        ),
        run=run,
        message=message,
    )


def handle_turn(
    db: Session, *, user_id: str, payload: AgentTurnRequest
) -> AgentTurnResponse:
    prep = prepare_turn(db, user_id=user_id, payload=payload)
    outcome = _dispatch(
        db,
        user_id=user_id,
        session=prep.session,
        decision=prep.decision,
        message=payload.message,
        options=payload.options,
        history=prep.history,
    )
    assistant: AgentMessage | None = outcome.message
    if assistant is None and outcome.reply is not None:
        assistant = agent_repository.create_message(
            db,
            message_id=new_id("agm"),
            session_id=prep.session.session_id,
            role="assistant",
            content=outcome.reply.content,
            kind=outcome.reply.kind,
            structured=outcome.reply.structured,
            sources=[source.model_dump(mode="json") for source in outcome.reply.sources] or None,
            file=outcome.reply.file.model_dump(mode="json") if outcome.reply.file else None,
            status="completed",
            meta={
                "intent": prep.decision.intent.value,
                "run_id": outcome.run.run_id if outcome.run else None,
                "result": outcome.reply.result,
                # 前端历史恢复靠它把确认门挂回原消息，缺失会补出重复卡片
                "pending_action_id": (
                    outcome.pending.action_id if outcome.pending else None
                ),
            },
        )
        agent_repository.touch_session(
            db, prep.session, last_message_at=assistant.created_at
        )
    return AgentTurnResponse(
        session_id=prep.session.session_id,
        intent=prep.decision,
        user_message=AgentMessageRead.model_validate(prep.user_message),
        assistant_message=(
            AgentMessageRead.model_validate(assistant) if assistant else None
        ),
        pending_action=(
            AgentPendingActionRead.model_validate(outcome.pending)
            if outcome.pending
            else None
        ),
        run=AgentRunRead.model_validate(outcome.run) if outcome.run else None,
        accepted=outcome.accepted,
    )


# ---------------------------------------------------------------- 流式


async def stream_turn(
    db: Session,
    *,
    user_id: str,
    payload: AgentTurnRequest,
    prep: _TurnPrep | None = None,
) -> AsyncIterator[tuple[str, dict]]:
    """SSE 事件流：intent → meta → delta* → pending_action/run → done。

    非对话意图（纪要/准备/行动项等）仍同步执行后一次性返回，前端按 `done`
    事件渲染；只有问答类走增量，避免长任务占用流。

    `prep` 由端点在首帧前准备（归属/会话类错误因此仍是统一 JSON 错误体），
    缺省时自行准备，便于直接调用。
    """
    if prep is None:
        prep = await run_in_threadpool(prepare_turn, db, user_id=user_id, payload=payload)
    yield "intent", prep.decision.model_dump(mode="json")

    if payload.options.quick_task or prep.decision.intent not in _CHAT_INTENTS:
        outcome = await run_in_threadpool(
            _dispatch,
            db,
            user_id=user_id,
            session=prep.session,
            decision=prep.decision,
            message=payload.message,
            options=payload.options,
            history=prep.history,
        )
        assistant = outcome.message or await run_in_threadpool(
            _persist_assistant,
            db,
            session=prep.session,
            outcome=outcome,
            decision=prep.decision,
        )
        if outcome.pending is not None:
            yield "pending_action", AgentPendingActionRead.model_validate(
                outcome.pending
            ).model_dump(mode="json")
        if outcome.run is not None:
            yield "run", AgentRunRead.model_validate(outcome.run).model_dump(mode="json")
        if outcome.reply is not None:
            yield "meta", {
                "sources": [
                    source.model_dump(mode="json") for source in outcome.reply.sources
                ],
                "insufficient_evidence": False,
            }
            yield "done", _done_payload(
                assistant=assistant,
                session_id=prep.session.session_id,
                intent=prep.decision,
                reply=outcome.reply,
            )
        return

    if not prep.session.meeting_id:
        raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)

    settings = get_settings()
    if prep.decision.intent is AgentIntent.web_search:
        run, message_row = await run_in_threadpool(
            _start_web_fallback,
            db,
            user_id=user_id,
            session=prep.session,
            question=payload.message,
            options=payload.options,
            require_confirmation=settings.web_search_require_confirmation,
        )
        if run.status == "waiting":
            pending = await run_in_threadpool(
                agent_repository.find_pending_action,
                db,
                session_id=prep.session.session_id,
                action_type="web_search",
            )
            if pending is not None:
                yield "pending_action", AgentPendingActionRead.model_validate(
                    pending
                ).model_dump(mode="json")
            yield "done", {
                "session_id": prep.session.session_id,
                "intent": prep.decision.model_dump(mode="json"),
                "message_id": message_row.message_id if message_row else None,
                "reply": {"content": "会议资料中没有找到相关证据。", "sources": []},
            }
            return
        if run.status == "failed":
            # 失败以 run 为唯一事实来源：发 error 事件，不当作成功渲染
            yield "error", {
                "error_code": run.error_code or "INTERNAL_ERROR",
                "message": run.error_message or "工作流执行失败",
                "retryable": True,
            }
            return
        state = dict(run.state or {})
        reply = AgentReply(
            content=str(state.get("answer") or "已完成。"),
            sources=_to_chat_sources(state.get("sources") or []),
        )
        assistant = message_row or await run_in_threadpool(
            _persist_assistant,
            db,
            session=prep.session,
            outcome=_DispatchOutcome(reply=reply, run=run),
            decision=prep.decision,
        )
        yield "meta", {
            "sources": [source.model_dump(mode="json") for source in reply.sources],
            "insufficient_evidence": bool(state.get("insufficient_evidence")),
        }
        yield "delta", {"text": reply.content}
        yield "done", _done_payload(
            assistant=assistant,
            session_id=prep.session.session_id,
            intent=prep.decision,
            reply=reply,
        )
        return

    scope = (
        "knowledge_base"
        if prep.decision.intent is AgentIntent.knowledge_search
        else payload.options.context_scope
    )
    # 思考模式：全局开关 ∧ 请求级开关
    thinking = bool(settings.ai_reasoning_enabled and payload.options.thinking)
    prepared_session = await run_in_threadpool(
        ai_chat_service.prepare_chat,
        db,
        meeting_id=prep.session.meeting_id,
        user_id=user_id,
        question=payload.message,
        context_scope=scope,
        include_sources=payload.options.include_sources,
        model=payload.options.model,
        history=prep.history if payload.options.include_history else [],
    )
    prepared = prepared_session.prepared
    trace = build_chat_trace(
        intent=prep.decision.intent.value,
        scope=scope,
        hits=len(prepared.sources),
        native=bool(
            thinking
            and reasoning_capable(
                prepared_session.model or "",
                getattr(prepared_session.service.llm, "api_base", "") or "",
            )
        ),
    )
    yield "meta", {
        # prepared.sources 是 dataclass，先归一为 ChatSource 再序列化
        "sources": [
            source.model_dump(mode="json")
            for source in _to_chat_sources(prepared.sources)
        ],
        "insufficient_evidence": not prepared.has_evidence,
        "trace": trace,
    }

    if (
        not prepared.has_evidence
        and settings.web_search_enabled
        and settings.web_search_require_confirmation
    ):
        pending, assistant = await run_in_threadpool(
            _persist_web_confirmation,
            db,
            session=prep.session,
            user_id=user_id,
            question=payload.message,
            intent=prep.decision.intent.value,
            options=payload.options,
        )
        yield "pending_action", AgentPendingActionRead.model_validate(
            pending
        ).model_dump(mode="json")
        yield "done", _done_payload(
            assistant=assistant,
            session_id=prep.session.session_id,
            intent=prep.decision,
            reply=AgentReply(content="会议资料中没有找到相关证据。"),
        )
        return

    chunks: list[str] = []
    reasoning_parts: list[str] = []
    stream_started = time.monotonic()
    try:
        async for chunk in prepared_session.service.answer_stream(
            prepared,
            allow_web=not settings.web_search_require_confirmation,
            thinking=thinking,
        ):
            if chunk.kind == "reasoning":
                reasoning_parts.append(chunk.text)
                yield "reasoning", {"text": chunk.text}
                continue
            chunks.append(chunk.text)
            yield "delta", {"text": chunk.text}
    except AppError as exc:
        yield "error", {
            "error_code": exc.error_code,
            "message": exc.message,
            "retryable": exc.retryable,
        }
        return
    except Exception:  # noqa: BLE001 — 流内异常统一归一，不裸抛
        logger.exception("Agent 流式回答异常 session=%s", prep.session.session_id)
        yield "error", {
            "error_code": "INTERNAL_ERROR",
            "message": "生成失败，请稍后重试",
            "retryable": True,
        }
        return

    answer = "".join(chunks)
    reply = AgentReply(
        content=answer,
        sources=_to_chat_sources(prepared.sources),
        reasoning="".join(reasoning_parts) or None,
        reasoning_ms=int((time.monotonic() - stream_started) * 1000),
        trace=trace["stages"],
    )
    assistant = await run_in_threadpool(
        _persist_assistant_independent,
        session_id=prep.session.session_id,
        reply=reply,
        decision=prep.decision,
    )
    yield "done", _done_payload(
        assistant=assistant,
        session_id=prep.session.session_id,
        intent=prep.decision,
        reply=reply,
    )


def _persist_web_confirmation(
    db: Session,
    *,
    session: AgentSession,
    user_id: str,
    question: str,
    intent: str,
    options: AgentTurnOptions | None = None,
) -> tuple[AgentPendingAction, AgentMessage]:
    """资料无证据时的确认门：登记 pending action 并落一条提示消息。"""
    pending = _create_pending(
        db,
        session=session,
        user_id=user_id,
        action_type="web_search",
        question=f"会议资料中没有找到「{question}」的相关证据，是否联网检索后再回答？",
        payload={
            "question": question,
            "options": (options or AgentTurnOptions()).model_dump(mode="json"),
        },
    )
    assistant = agent_repository.create_message(
        db,
        message_id=new_id("agm"),
        session_id=session.session_id,
        role="assistant",
        content="会议资料中没有找到相关证据。",
        status="completed",
        meta={"intent": intent, "pending_action_id": pending.action_id},
    )
    agent_repository.touch_session(
        db, session, last_message_at=assistant.created_at
    )
    return pending, assistant


def _persist_assistant(
    db: Session,
    *,
    session: AgentSession,
    outcome: _DispatchOutcome,
    decision: AgentIntentDecision,
) -> AgentMessage | None:
    if outcome.reply is None:
        return None
    assistant = agent_repository.create_message(
        db,
        message_id=new_id("agm"),
        session_id=session.session_id,
        role="assistant",
        content=outcome.reply.content,
        kind=outcome.reply.kind,
        structured=outcome.reply.structured,
        sources=[source.model_dump(mode="json") for source in outcome.reply.sources] or None,
        file=outcome.reply.file.model_dump(mode="json") if outcome.reply.file else None,
        status="completed",
        meta={
            "intent": decision.intent.value,
            "run_id": outcome.run.run_id if outcome.run else None,
            "result": outcome.reply.result,
            "pending_action_id": (
                outcome.pending.action_id if outcome.pending else None
            ),
        },
    )
    agent_repository.touch_session(
        db, session, last_message_at=assistant.created_at
    )
    return assistant


@dataclass(frozen=True)
class _AssistantRef:
    """独立会话落库后的轻量引用。

    独立 Session 关闭后 ORM 实例已 detached，再访问属性会触发刷新并抛
    `DetachedInstanceError`；这里只保留 `_done_payload` 需要的 message_id。
    """

    message_id: str


def _persist_assistant_independent(
    *,
    session_id: str,
    reply: AgentReply,
    decision: AgentIntentDecision,
) -> _AssistantRef | None:
    """流式收尾使用独立会话：请求会话可能已随响应关闭。"""
    from app.services import task_runner

    db = task_runner.session_factory()
    try:
        session = agent_repository.get_session(db, session_id)
        if session is None:
            return None
        # 思考过程：原生推理与执行步骤随消息保存，历史恢复后可折叠回看
        meta = {"intent": decision.intent.value}
        if reply.reasoning:
            meta["reasoning"] = reply.reasoning
        if reply.reasoning_ms is not None:
            meta["reasoning_ms"] = reply.reasoning_ms
        if reply.trace:
            meta["trace"] = reply.trace
        assistant = agent_repository.create_message(
            db,
            message_id=new_id("agm"),
            session_id=session_id,
            role="assistant",
            content=reply.content,
            kind=reply.kind,
            structured=reply.structured,
            sources=[source.model_dump(mode="json") for source in reply.sources] or None,
            file=reply.file.model_dump(mode="json") if reply.file else None,
            status="completed",
            meta=meta,
        )
        message_id = assistant.message_id
        agent_repository.touch_session(
            db, session, last_message_at=assistant.created_at
        )
        return _AssistantRef(message_id=message_id)
    except Exception:  # noqa: BLE001 — 落库失败不影响已输出的回答
        logger.exception("Agent 流式回答落库失败 session=%s", session_id)
        db.rollback()
        return None
    finally:
        db.close()


def _done_payload(
    *,
    assistant: AgentMessage | _AssistantRef | None,
    session_id: str,
    intent: AgentIntentDecision,
    reply: AgentReply,
) -> dict:
    return {
        "session_id": session_id,
        "intent": intent.model_dump(mode="json"),
        "message_id": assistant.message_id if assistant else None,
        "reply": {
            "content": reply.content,
            "kind": reply.kind,
            "structured": reply.structured,
            "sources": [source.model_dump(mode="json") for source in reply.sources],
            "note": reply.note,
            "file": reply.file.model_dump(mode="json") if reply.file else None,
            "result": reply.result,
            "reasoning": reply.reasoning,
            "reasoning_ms": reply.reasoning_ms,
            "trace": reply.trace,
        },
    }


# ---------------------------------------------------------------- 确认门


def _claim_pending(
    db: Session, action_id: str, user_id: str, *, status: str
) -> AgentPendingAction:
    """原子地把待确认动作置为终态（approved / rejected）。

    检查与置位由一次条件 UPDATE 完成（`claim_pending_action`），两个并发
    请求只有一个能改成功，另一个按真实原因返回 404 / 409。
    """
    now = datetime.now(UTC)
    action = agent_repository.claim_pending_action(
        db, action_id=action_id, user_id=user_id, status=status, now=now
    )
    if action is not None:
        return action

    fresh = agent_repository.get_owned_pending_action(db, action_id, user_id)
    if fresh is None:
        raise resource_not_found("待确认动作")
    if fresh.status != "pending":
        raise AppError("BUSINESS_RULE_VIOLATION", "该动作已处理", http_status=409)
    # 仍为 pending 却没被更新 → 只可能是已过期：补记过期状态后拒绝
    agent_repository.update_pending_action(
        db, fresh, status="expired", decided_at=now
    )
    raise AppError(
        "BUSINESS_RULE_VIOLATION", "该动作已过期，请重新发起", http_status=409
    )


def approve_pending_action(
    db: Session, *, action_id: str, user_id: str, note: str | None = None
) -> AgentTurnResponse:
    action = _claim_pending(db, action_id, user_id, status="approved")
    session = get_owned_session(db, action.session_id, user_id)

    if action.action_type == "web_search":
        question = str((action.payload or {}).get("question") or "")
        # 批准后的执行必须沿用发起时的选项（模型/思考模式/模板），
        # 否则回答会退回默认配置，与用户选择不一致
        options = AgentTurnOptions.model_validate(
            (action.payload or {}).get("options") or {}
        )
        run = (
            agent_repository.get_owned_run(db, action.run_id, user_id)
            if action.run_id
            else None
        )
        if run is not None and run.status == "waiting":
            # 工作流停在确认门：原地恢复，不新建 run（保留原 state 与执行选项）
            state = dict(run.state or {})
            state.setdefault("options", options.model_dump(mode="json"))
            state["_next_step"] = "web_search"
            state["approved"] = True
            agent_repository.update_run(
                db, run, status="running", state=state
            )
        else:
            run = agent_repository.create_run(
                db,
                run_id=new_id("agr"),
                session_id=session.session_id,
                user_id=user_id,
                meeting_id=session.meeting_id,
                workflow="web_fallback",
                state={
                    "question": question,
                    "require_confirmation": True,
                    "approved": True,
                    "_next_step": "web_search",
                    "meeting_id": session.meeting_id,
                    "scene": session.scene,
                    "options": options.model_dump(mode="json"),
                },
            )
            agent_repository.update_run(
                db, run, status="running", started_at=datetime.now(UTC)
            )
        resumed_state = dict(run.state or {})
        context = AgentContext(
            db=db,
            user_id=user_id,
            session_id=session.session_id,
            meeting_id=session.meeting_id,
            scene=session.scene,
            options=AgentTurnOptions.model_validate(
                resumed_state.get("options") or {}
            ),
            question=question,
        )
        _, workflow_message = _run_workflow(db, run=run, context=context)
        db.refresh(run)
        _raise_if_run_failed(run)
        state = dict(run.state or {})
        reply = AgentReply(
            content=str(state.get("answer") or "根据现有材料无法确认该问题的答案。"),
            sources=_to_chat_sources(state.get("sources") or []),
            note="以上回答基于联网检索，仅供参考。" if state.get("sources") else None,
        )
        assistant = workflow_message or _persist_assistant(
            db,
            session=session,
            outcome=_DispatchOutcome(reply=reply, run=run),
            decision=AgentIntentDecision(
                intent=AgentIntent.web_search, confidence=1.0, source="explicit"
            ),
        )
        return AgentTurnResponse(
            session_id=session.session_id,
            intent=AgentIntentDecision(
                intent=AgentIntent.web_search, confidence=1.0, source="explicit"
            ),
            user_message=_last_user_message(db, session.session_id),
            assistant_message=(
                AgentMessageRead.model_validate(assistant) if assistant else None
            ),
            run=AgentRunRead.model_validate(run),
        )

    if action.action_type == "confirm_transcript":
        audio_id = str((action.payload or {}).get("audio_id") or "")
        audio = audio_service.confirm_audio(db, audio_id, user_id)
        run = (
            agent_repository.get_owned_run(db, action.run_id, user_id)
            if action.run_id
            else None
        )
        if run is None:
            run = agent_repository.create_run(
                db,
                run_id=new_id("agr"),
                session_id=session.session_id,
                user_id=user_id,
                meeting_id=session.meeting_id,
                workflow="transcribe_to_minutes",
                state={
                    "audio_id": audio.audio_id,
                    "meeting_id": audio.meeting_id,
                    "record_id": audio.record_id,
                    "include_action_items": get_settings().agent_auto_action_items_enabled,
                    "scene": session.scene,
                },
            )
        state = dict(run.state or {})
        state.update(
            {
                "audio_id": audio.audio_id,
                "meeting_id": audio.meeting_id,
                "record_id": audio.record_id,
                "_next_step": "generate_minutes_draft",
            }
        )
        agent_repository.update_run(
            db, run, status="running", state=state, started_at=datetime.now(UTC)
        )
        context = AgentContext(
            db=db,
            user_id=user_id,
            session_id=session.session_id,
            meeting_id=audio.meeting_id,
            scene=session.scene,
            options=AgentTurnOptions(),
        )
        _, workflow_message = _run_workflow(db, run=run, context=context)
        db.refresh(run)
        _raise_if_run_failed(run)
        state = dict(run.state or {})
        reply = AgentReply(
            content=str(state.get("content") or "已完成。"),
            kind="minutes",
        )
        assistant = workflow_message or _persist_assistant(
            db,
            session=session,
            outcome=_DispatchOutcome(reply=reply, run=run),
            decision=AgentIntentDecision(
                intent=AgentIntent.minutes_generate, confidence=1.0, source="explicit"
            ),
        )
        return AgentTurnResponse(
            session_id=session.session_id,
            intent=AgentIntentDecision(
                intent=AgentIntent.minutes_generate, confidence=1.0, source="explicit"
            ),
            user_message=_last_user_message(db, session.session_id),
            assistant_message=(
                AgentMessageRead.model_validate(assistant) if assistant else None
            ),
            run=AgentRunRead.model_validate(run),
        )

    raise AppError("VALIDATION_ERROR", "不支持的确认动作", http_status=422)


def reject_pending_action(
    db: Session, *, action_id: str, user_id: str, note: str | None = None
) -> AgentTurnResponse:
    action = _claim_pending(db, action_id, user_id, status="rejected")
    session = get_owned_session(db, action.session_id, user_id)
    content = (
        "已取消联网检索，仍然只依据会议资料回答。"
        if action.action_type == "web_search"
        else "已取消本次操作。"
    )
    if note:
        content = f"{content}（{note}）"
    assistant = agent_repository.create_message(
        db,
        message_id=new_id("agm"),
        session_id=session.session_id,
        role="assistant",
        content=content,
        status="completed",
        meta={"intent": "clarify", "rejected_action": action.action_id},
    )
    agent_repository.touch_session(
        db, session, last_message_at=assistant.created_at
    )
    if action.run_id:
        run = agent_repository.get_owned_run(db, action.run_id, user_id)
        if run is not None and run.status in ("pending", "running", "waiting"):
            agent_repository.update_run(
                db, run, status="cancelled", finished_at=datetime.now(UTC)
            )
    return AgentTurnResponse(
        session_id=session.session_id,
        intent=AgentIntentDecision(
            intent=AgentIntent.clarify, confidence=1.0, source="explicit"
        ),
        user_message=_last_user_message(db, session.session_id),
        assistant_message=AgentMessageRead.model_validate(assistant),
    )


def _last_user_message(db: Session, session_id: str) -> AgentMessageRead | None:
    messages = agent_repository.list_messages(
        db, session_id=session_id, limit=50, offset=0
    )
    for message in reversed(messages):
        if message.role == "user":
            return AgentMessageRead.model_validate(message)
    return None


# ---------------------------------------------------------------- 工作流执行（worker）


def execute_run(
    db: Session, run_id: str, *, progress_cb: Any = None
) -> None:
    run = db.execute(
        select(AgentRun).where(AgentRun.run_id == run_id)
    ).scalar_one_or_none()
    if run is None:
        logger.error("Agent 工作流不存在 run_id=%s", run_id)
        return
    if run.status != "pending":
        logger.warning("Agent 工作流状态非 pending，跳过 run_id=%s status=%s", run_id, run.status)
        return
    session = agent_repository.get_session(db, run.session_id)
    if session is None:
        agent_repository.update_run(
            db, run, status="failed", error_code="RESOURCE_NOT_FOUND", error_message="会话不存在"
        )
        return
    state = dict(run.state or {})
    options = AgentTurnOptions.model_validate(state.get("options") or {})
    context = AgentContext(
        db=db,
        user_id=run.user_id,
        session_id=run.session_id,
        meeting_id=run.meeting_id or session.meeting_id,
        scene=session.scene,
        options=options,
        question=str(state.get("question") or ""),
    )
    agent_repository.update_run(
        db, run, status="running", started_at=datetime.now(UTC)
    )
    if progress_cb:
        progress_cb(5)
    try:
        _run_workflow(db, run=run, context=context)
    except AppError as exc:
        db.rollback()
        agent_repository.update_run(
            db,
            run,
            status="failed",
            error_code=exc.error_code,
            error_message=exc.message,
            finished_at=datetime.now(UTC),
        )
        raise
    if progress_cb:
        progress_cb(100)


# ---------------------------------------------------------------- 自动纪要


def trigger_auto_minutes(
    db: Session,
    background_tasks: BackgroundTasks | None,
    *,
    user_id: str,
    audio: Any,
) -> AgentRun | None:
    """转写确认后触发「转写 → 纪要草稿」工作流；只落 draft，不自动确认。"""
    settings = get_settings()
    if not settings.agent_enabled or not settings.agent_auto_minutes_enabled:
        return None
    if not audio.record_id:
        return None
    session = ensure_session(
        db,
        user_id=user_id,
        session_id=None,
        scene="minutes",
        meeting_id=audio.meeting_id,
    )
    existing = agent_repository.find_active_run(
        db,
        session_id=session.session_id,
        workflow="transcribe_to_minutes",
        resource_id=audio.audio_id,
    )
    if existing is not None:
        return existing
    run = agent_repository.create_run(
        db,
        run_id=new_id("agr"),
        session_id=session.session_id,
        user_id=user_id,
        meeting_id=audio.meeting_id,
        workflow="transcribe_to_minutes",
        state={
            "resource_id": audio.audio_id,
            "audio_id": audio.audio_id,
            "meeting_id": audio.meeting_id,
            "record_id": audio.record_id,
            "include_action_items": settings.agent_auto_action_items_enabled,
            "scene": session.scene,
        },
    )
    job = job_service.enqueue(
        db,
        background_tasks,
        user_id=user_id,
        job_type="agent_workflow",
        resource_type="agent_run",
        resource_id=run.run_id,
        fn=job_tasks.agent_workflow(run.run_id),
        payload={"run_id": run.run_id},
        priority=10,
    )
    agent_repository.update_run(db, run, job_id=job.job_id)
    db.refresh(run)
    return run


# ---------------------------------------------------------------- 运行查询


def get_owned_run(db: Session, run_id: str, user_id: str) -> AgentRun:
    run = agent_repository.get_owned_run(db, run_id, user_id)
    if run is None:
        raise resource_not_found("Agent 运行")
    return run


def list_run_steps(db: Session, run_id: str, user_id: str):
    get_owned_run(db, run_id, user_id)
    return agent_repository.list_steps(db, run_id=run_id)


def list_pending_actions(
    db: Session, *, session_id: str, user_id: str, status: str | None = "pending"
) -> list[AgentPendingAction]:
    get_owned_session(db, session_id, user_id)
    return agent_repository.list_pending_actions(
        db, session_id=session_id, status=status
    )


def cancel_run(db: Session, run_id: str, user_id: str) -> AgentRun:
    run = get_owned_run(db, run_id, user_id)
    if run.status in ("succeeded", "failed", "cancelled"):
        return run
    return agent_repository.update_run(
        db, run, status="cancelled", finished_at=datetime.now(UTC)
    )


class _DbStepRecorder:
    """把工作流步骤轨迹写入 `agent_run_steps`。"""

    def __init__(self, db: Session, run_id: str) -> None:
        self._db = db
        self._run_id = run_id

    def record(
        self,
        *,
        step_name: str,
        status: str,
        attempt: int,
        input: dict | None,
        output: dict | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        agent_repository.create_step(
            self._db,
            step_id=new_id("ast"),
            run_id=self._run_id,
            step_name=step_name,
            status=status,
            attempt=attempt,
            input=input,
            output=output,
            error_code=error_code,
            error_message=error_message,
            finished_at=datetime.now(UTC) if status != "retrying" else None,
        )
