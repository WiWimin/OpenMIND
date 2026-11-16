from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import audit
from app.ai.chat import ChatAnswer, ChatPreparation, ChatService, RecordContext
from app.ai.prompts import build_organize, build_quick_task
from app.ai.rag import VectorRetriever
from app.ai.rag.relevance import RECORD_MIN_SCORE, char_overlap
from app.ai.structured import run_structured
from app.core.exceptions import AppError
from app.repositories import agent_repository, record_repository
from app.schemas.chat import (
    OrganizeTask,
    PolishSuggestions,
    SummaryStructured,
)
from app.services import ai_audit_service, audio_service, meeting_service, memory_service
from app.services.model_config_service import (
    ModelConfig,
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)

logger = logging.getLogger(__name__)

# 参与结构化解析的任务：LLM 原始输出需为 JSON
_STRUCTURED_TASKS = {OrganizeTask.summary, OrganizeTask.polish}

_PRIORITY_VALUES = {"high", "medium", "low"}
_CONFIDENCE_VALUES = {"high", "medium", "low"}


def _validate_summary(value: SummaryStructured) -> list[str]:
    """summary 业务字段校验：任务非空、优先级取值合法、原文摘录非空白。"""
    errors: list[str] = []
    for index, item in enumerate(value.action_items):
        if not item.task.strip():  # pragma: no cover — schema min_length 已拦截
            errors.append(f"action_items.{index}.task 不能为空")
        if item.priority not in _PRIORITY_VALUES:
            errors.append(f"action_items.{index}.priority 必须是 high/medium/low")
        if item.source_quote is not None and not item.source_quote.strip():
            errors.append(f"action_items.{index}.source_quote 为空时应使用 null")
    return errors


def _validate_polish(value: PolishSuggestions) -> list[str]:
    """polish 业务字段校验：原文/建议非空、置信度取值合法。"""
    errors: list[str] = []
    for index, item in enumerate(value.root):
        if not item.original.strip():
            errors.append(f"{index}.original 不能为空")
        if not item.suggested.strip():
            errors.append(f"{index}.suggested 不能为空")
        if item.confidence not in _CONFIDENCE_VALUES:
            errors.append(f"{index}.confidence 必须是 high/medium/low")
    return errors


@dataclass(frozen=True)
class OrganizeOutcome:
    task: OrganizeTask
    content: str
    structured: dict | list | None
    source_record_ids: list[str]


def _chat_service(db: Session, user_id: str, model_override: str | None = None) -> ChatService:
    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.chat, model_override=model_override
    )
    return ChatService(build_llm_client(config), VectorRetriever(db, user_id))


def _run_organize_llm(messages: list[dict[str, str]], config: ModelConfig) -> str:
    return build_llm_client(config).chat(messages, scene="organize").text


def _recent_record_context(
    db: Session, meeting_id: str, *, limit: int = 20, char_limit: int = 8000
) -> list[RecordContext]:
    """最近记录（不看相关性）：供「整理记录」等把记录当输入源的功能使用。"""
    records = record_repository.list_recent_by_meeting(db, meeting_id, limit=limit)
    selected: list[RecordContext] = []
    used = 0
    for record in reversed(records):
        if used + len(record.content) > char_limit:
            break
        selected.append(
            RecordContext(
                meeting_id=meeting_id,
                record_id=record.record_id,
                content=record.content,
            )
        )
        used += len(record.content)
    return selected


# 问答证据门：只注入与问题词面相关的记录，否则「有记录」等于「永远有证据」
_RECORD_KEEP = 5
_RECORD_CHAR_LIMIT = 4000


def _relevant_record_context(
    db: Session,
    meeting_id: str,
    *,
    question: str,
    limit: int = 20,
    keep: int = _RECORD_KEEP,
    char_limit: int = _RECORD_CHAR_LIMIT,
) -> list[RecordContext]:
    """按问题相关性筛选最近记录；无相关记录时返回空，让证据门真正生效。

    记录未入向量库，先用词面覆盖度（`char_overlap`）做廉价预筛；
    过短的问句（bigram 不足）按 1.0 视为相关，避免寒暄/指代类提问被
    误判为「无证据」而误触联网确认门。
    """
    records = record_repository.list_recent_by_meeting(db, meeting_id, limit=limit)
    relevant = [
        record
        for record in records
        if char_overlap(question, record.content) >= RECORD_MIN_SCORE
    ]
    if not relevant:
        return []
    # 最新在前取 top-k，再恢复为时间顺序（与 _recent_record_context 一致）
    relevant.sort(
        key=lambda record: (record.created_at, record.record_id), reverse=True
    )
    chosen = list(reversed(relevant[:keep]))
    selected: list[RecordContext] = []
    used = 0
    for record in chosen:
        if used + len(record.content) > char_limit:
            break
        selected.append(
            RecordContext(
                meeting_id=meeting_id,
                record_id=record.record_id,
                content=record.content,
            )
        )
        used += len(record.content)
    return selected


# 多轮上下文预算：条数 + 字符双上限，防止历史挤占资料上下文
_HISTORY_MAX_MESSAGES = 6
_HISTORY_MAX_CHARS = 3000


def load_history(
    db: Session,
    session_id: str,
    *,
    exclude_message_id: str | None = None,
    limit: int = _HISTORY_MAX_MESSAGES,
    char_limit: int = _HISTORY_MAX_CHARS,
) -> list[dict[str, str]]:
    """取本会话最近几轮作为问答历史（服务端为事实来源，前端不回传）。

    只放行已完成的 user/assistant 消息；确认门提示、失败消息与当前这一轮
    都不注入，避免把「是否联网检索？」当成助手结论。
    """
    fetched = agent_repository.list_messages(
        db, session_id=session_id, limit=max(limit, 1) * 4, offset=0
    )
    picked: list[dict[str, str]] = []
    used = 0
    for message in reversed(fetched):
        if len(picked) >= limit:
            break
        if message.message_id == exclude_message_id:
            continue
        if message.status != "completed" or message.role not in ("user", "assistant"):
            continue
        if (message.meta or {}).get("pending_action_id"):
            continue
        content = (message.content or "").strip()
        if not content:
            continue
        remaining = char_limit - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining]
            picked.append({"role": message.role, "content": content})
            break
        picked.append({"role": message.role, "content": content})
        used += len(content)
    picked.reverse()
    return picked


def _resolve_organize_transcripts(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    text: str,
    audio_id: str | None,
    record_ids: list[str],
) -> tuple[list[str], list[str]]:
    """输入源三级回退：text > audio_id > record_ids（空 = 最近记录）。"""
    if text and text.strip():
        return [text.strip()], []
    if audio_id:
        audio = audio_service.get_owned_audio(db, audio_id, user_id)
        transcript = (audio.transcript or "").strip()
        if not transcript:
            raise AppError(
                "VALIDATION_ERROR", "该音频尚未成功转写，没有可用的文本", http_status=422
            )
        return [transcript], []
    if record_ids:
        records = record_repository.list_by_ids(db, meeting_id, record_ids)
        if not records:
            raise AppError(
                "VALIDATION_ERROR", "未找到可整理的会议记录", http_status=422
            )
        return [record.content for record in records], [
            record.record_id for record in records
        ]
    contexts = _recent_record_context(db, meeting_id)
    if not contexts:
        raise AppError("VALIDATION_ERROR", "没有可用的会议记录", http_status=422)
    return [ctx.content for ctx in contexts], [ctx.record_id for ctx in contexts]


def chat(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    question: str,
    context_scope: str,
    include_sources: bool,
    model: str | None = None,
    mode: str = "plan",
    allow_web: bool = True,
    history: list[dict[str, str]] | None = None,
) -> ChatAnswer:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    service = _chat_service(db, user_id, model)
    # 测试替身可能没有 llm 属性：兜底为空串（LLMClient 调用时会覆盖事件字段）
    llm = getattr(service, "llm", None)
    with ai_audit_service.audit_call(
        db,
        user_id=user_id,
        scene="chat",
        model=getattr(llm, "model", "") or "",
        provider=audit.provider_host(getattr(llm, "api_base", "") or ""),
    ):
        return service.answer(
            question,
            user_id=user_id,
            scope=context_scope,
            current_meeting_id=meeting_id,
            records=(
                []
                if context_scope == "knowledge_base"
                else _relevant_record_context(db, meeting_id, question=question)
            ),
            memory_context=memory_service.memory_context_for(db, user_id, "chat"),
            history=history,
            mode=mode,
            allow_web=allow_web,
        )


@dataclass(frozen=True)
class ChatStreamSession:
    """流式问答的会话内准备结果：归属校验、检索、记忆均已完成（纯内存）。"""

    service: ChatService
    prepared: ChatPreparation
    include_sources: bool
    model: str | None


def prepare_chat(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    question: str,
    context_scope: str,
    include_sources: bool,
    model: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> ChatStreamSession:
    """同步校验与上下文收集：404 归属、400 模型未配置在流开始前返回。"""
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    service = _chat_service(db, user_id, model)
    prepared = service.prepare(
        question,
        user_id=user_id,
        scope=context_scope,
        current_meeting_id=meeting_id,
        records=(
            []
            if context_scope == "knowledge_base"
            else _relevant_record_context(db, meeting_id, question=question)
        ),
        memory_context=memory_service.memory_context_for(db, user_id, "chat"),
        history=history,
    )
    return ChatStreamSession(
        service=service,
        prepared=prepared,
        include_sources=include_sources,
        model=service.llm.model,
    )


def organize(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    record_ids: list[str],
    style: str = "",
    task: OrganizeTask = OrganizeTask.organize,
    text: str = "",
    instruction: str = "",
    audio_id: str | None = None,
    model: str | None = None,
) -> OrganizeOutcome:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    transcripts, source_ids = _resolve_organize_transcripts(
        db,
        meeting_id=meeting_id,
        user_id=user_id,
        text=text,
        audio_id=audio_id,
        record_ids=record_ids,
    )
    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.chat, model_override=model
    )
    messages = build_organize(
        {
            "record_transcripts": transcripts,
            "style": style,
            "task": task.value,
            "instruction": instruction,
        }
    )
    with ai_audit_service.audit_call(
        db,
        user_id=user_id,
        scene="organize",
        # 测试替身可能返回非 ModelConfig 对象：防御式取值，LLMClient 调用时会覆盖
        model=getattr(config, "llm_model", "") or "",
        provider=audit.provider_host(getattr(config, "llm_api_base", "") or ""),
    ):
        if task not in _STRUCTURED_TASKS:
            raw = _run_organize_llm(messages, config)
            return OrganizeOutcome(
                task=task,
                content=raw.strip() or "（未生成有效内容）",
                structured=None,
                source_record_ids=source_ids,
            )

        # summary/polish：结构化管线（预处理 → schema+业务校验 → 1 次修复重试 → 降级原文）
        raw_texts: list[str] = []

        def _fetch(current: list[dict[str, str]]) -> str:
            raw = _run_organize_llm(current, config)
            raw_texts.append(raw)
            return raw

        if task is OrganizeTask.summary:
            parsed = run_structured(
                _fetch,
                messages,
                SummaryStructured,
                scene="organize_summary",
                validator=_validate_summary,
                on_failure="degrade",
            )
            structured: dict | list | None = (
                parsed.model_dump() if parsed is not None else None
            )
        else:
            parsed_polish = run_structured(
                _fetch,
                messages,
                PolishSuggestions,
                scene="organize_polish",
                validator=_validate_polish,
                on_failure="degrade",
            )
            structured = (
                parsed_polish.model_dump() if parsed_polish is not None else None
            )

        # 降级时返回首次尝试的原文（修复重试的输出不作为兜底正文）
        fallback = raw_texts[0] if raw_texts else ""
        content = (
            "" if structured is not None else (fallback.strip() or "（未生成有效内容）")
        )
        return OrganizeOutcome(
            task=task,
            content=content,
            structured=structured,
            source_record_ids=source_ids,
        )


def quick_task(
    db: Session,
    *,
    user_id: str,
    text: str,
    task: str,
    instruction: str = "",
    model: str | None = None,
) -> str:
    """简单文本任务（润色/精简/改写/翻译）：单次 LLM，无检索、无落库。

    与 `organize` 的边界：本函数只处理调用方提供的文本片段，不读取会议记录，
    不写回原始数据；输出由前端展示或复制，用户自行决定是否采用。
    """
    if not text.strip():
        raise AppError("VALIDATION_ERROR", "请先输入需要处理的文本", http_status=422)
    config = resolve_model_config(
        db, user_id, purpose=ModelPurpose.chat, model_override=model
    )
    messages = build_quick_task(
        {"task": task, "text": text, "instruction": instruction}
    )
    with ai_audit_service.audit_call(
        db,
        user_id=user_id,
        scene="quick_task",
        model=getattr(config, "llm_model", "") or "",
        provider=audit.provider_host(getattr(config, "llm_api_base", "") or ""),
    ):
        raw = build_llm_client(config).chat(messages, scene="quick_task").text
    return raw.strip() or "（未生成有效内容）"
