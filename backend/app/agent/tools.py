"""工具注册表：把既有 service 能力包装成工作流步骤可调用的纯函数。

边界（`docs/agent-framework.md 3.5`）：

- 工具只调用 `services/` 与 `ai/`，不直接写业务表；
- 需要确认的工具（联网检索）通过 `WaitForConfirmation` 停下，不自行执行；
- 工具输出只作为数据，不作为指令（防间接注入）；
- 权限校验由被调用的 service 统一完成（`get_mutable_meeting` / `get_owned_*`）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agent.workflow import WaitForConfirmation
from app.ai import audit
from app.ai.prompts import build_chat, build_web_chat
from app.ai.websearch import web_search
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.schemas.agent import AgentTurnOptions
from app.schemas.minutes import MinutesGenerateRequest
from app.services import (
    action_item_service,
    ai_audit_service,
    ai_chat_service,
    audio_service,
    minutes_service,
)
from app.services.model_config_service import (
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)
from app.utils import storage

_REFUSAL = "根据现有材料无法确认该问题的答案。"
_WEB_NOTICE = "你的会议资料中未找到相关证据。以下回答基于联网检索，仅供参考："


@dataclass
class AgentContext:
    """一次 Agent 执行的上下文（请求内或 worker 内）。"""

    db: Session
    user_id: str
    session_id: str
    meeting_id: str | None
    scene: str
    options: AgentTurnOptions = field(default_factory=AgentTurnOptions)
    question: str = ""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    run: Callable[[AgentContext, dict], dict]
    description: str = ""
    requires_confirmation: bool = False


def _require_meeting(context: AgentContext) -> str:
    if not context.meeting_id:
        raise AppError("VALIDATION_ERROR", "请先选择一场会议", http_status=422)
    return context.meeting_id


def _source_payload(source: Any) -> dict[str, Any]:
    """检索来源归一为可 JSON 化 dict（dataclass / pydantic 两种形态）。"""
    if hasattr(source, "model_dump"):
        return source.model_dump()
    if is_dataclass(source) and not isinstance(source, type):
        return asdict(source)
    return dict(getattr(source, "__dict__", {}))


def _llm_client(context: AgentContext):
    config = resolve_model_config(
        context.db,
        context.user_id,
        purpose=ModelPurpose.chat,
        model_override=context.options.model,
    )
    return build_llm_client(config), config


# ---------------------------------------------------------------- 问答 / 联网


def retrieve(context: AgentContext, inputs: dict) -> dict:
    meeting_id = _require_meeting(context)
    question = str(inputs.get("question") or context.question).strip()
    prepared_session = ai_chat_service.prepare_chat(
        context.db,
        meeting_id=meeting_id,
        user_id=context.user_id,
        question=question,
        context_scope=context.options.context_scope,
        include_sources=context.options.include_sources,
        model=context.options.model,
    )
    prepared = prepared_session.prepared
    return {
        "question": question,
        "contexts": prepared.contexts,
        "memory_context": prepared.memory_context,
        "sources": [_source_payload(source) for source in prepared.sources],
        "has_evidence": prepared.has_evidence,
    }


def answer_from_context(context: AgentContext, inputs: dict) -> dict:
    question = str(inputs.get("question") or context.question)
    contexts = list(inputs.get("contexts") or [])
    memory_context = str(inputs.get("memory_context") or "")
    # 与问答链路保持一致的多轮上下文；当前这轮的提问已在 question 里，剔除避免重复
    history = ai_chat_service.load_history(context.db, context.session_id)
    if history and history[-1]["role"] == "user" and history[-1]["content"] == question:
        history = history[:-1]
    client, config = _llm_client(context)
    with ai_audit_service.audit_call(
        context.db,
        user_id=context.user_id,
        scene="chat",
        model=config.llm_model,
        provider=audit.provider_host(config.llm_api_base),
    ):
        answer = client.chat(
            build_chat(
                {
                    "question": question,
                    "contexts": contexts,
                    "memory_context": memory_context,
                    "history": history,
                }
            ),
            scene="chat",
        ).text
    return {
        "answer": answer,
        "insufficient_evidence": False,
        "kind": None,
    }


def ask_web_permission(context: AgentContext, inputs: dict) -> dict:
    question = str(inputs.get("question") or context.question)
    raise WaitForConfirmation(
        action_type="web_search",
        question=f"会议资料中没有找到「{question}」的相关证据，是否联网检索后再回答？",
        # 批准时沿用发起时的执行选项（模型/思考开关/模板），避免退回默认配置
        payload={
            "question": question,
            "options": context.options.model_dump(mode="json"),
        },
    )


def web_search_tool(context: AgentContext, inputs: dict) -> dict:
    question = str(inputs.get("question") or context.question)
    results = web_search(question)
    return {
        "web_results": [
            {"title": item.title, "url": item.url, "snippet": item.snippet}
            for item in results
        ],
        "has_web": bool(results),
    }


def answer_with_web(context: AgentContext, inputs: dict) -> dict:
    question = str(inputs.get("question") or context.question)
    results = list(inputs.get("web_results") or [])
    if not results:
        return {"answer": _REFUSAL, "insufficient_evidence": True, "sources": []}
    client, config = _llm_client(context)
    with ai_audit_service.audit_call(
        context.db,
        user_id=context.user_id,
        scene="chat",
        model=config.llm_model,
        provider=audit.provider_host(config.llm_api_base),
    ):
        answer = client.chat(
            build_web_chat({"question": question, "sources": results}),
            scene="chat",
        ).text
    sources = [
        {
            "meeting_id": None,
            "material_id": None,
            "record_id": None,
            "excerpt": item.get("snippet") or item.get("title", "")[:200],
            "origin": "web",
            "url": item.get("url"),
            "title": item.get("title"),
        }
        for item in results
    ]
    return {
        "answer": f"{_WEB_NOTICE}\n\n{answer}",
        "insufficient_evidence": True,
        "sources": sources,
        "kind": None,
    }


def refuse(context: AgentContext, inputs: dict) -> dict:  # noqa: ARG001
    return {"answer": _REFUSAL, "insufficient_evidence": True, "sources": []}


# ---------------------------------------------------------------- 简单文本任务


def prompt_task(context: AgentContext, inputs: dict) -> dict:
    """单次 LLM 的文本处理（润色/精简/改写/翻译），无检索、无落库。"""
    task = str(inputs.get("task") or context.options.quick_task or "polish")
    text = str(inputs.get("text") or context.question or "").strip()
    content = ai_chat_service.quick_task(
        context.db,
        user_id=context.user_id,
        text=text,
        task=task,
        instruction=str(inputs.get("instruction") or ""),
        model=context.options.model,
    )
    return {"content": content, "kind": None}


# ---------------------------------------------------------------- 转写 → 纪要


def load_audio(context: AgentContext, inputs: dict) -> dict:
    audio_id = str(inputs.get("audio_id") or "").strip()
    if not audio_id:
        raise AppError("VALIDATION_ERROR", "缺少音频标识", http_status=422)
    audio = audio_service.get_owned_audio(context.db, audio_id, context.user_id)
    return {
        "audio_id": audio.audio_id,
        "meeting_id": audio.meeting_id,
        "transcript": audio.transcript or "",
        "audio_status": audio.status,
        "record_id": audio.record_id,
        "file_name": audio.file_name,
        "storage_key": audio.storage_key,
    }


def transcribe_audio(context: AgentContext, inputs: dict) -> dict:
    audio_id = str(inputs.get("audio_id") or "")
    audio = audio_service.get_owned_audio(context.db, audio_id, context.user_id)
    if (audio.transcript or "").strip():
        return {"transcript": audio.transcript or "", "transcribed": True}
    try:
        content = storage.read_bytes(get_settings().storage_dir, audio.storage_key)
    except OSError:
        raise AppError(
            "RESOURCE_NOT_FOUND", "原始文件已丢失，请重新上传", http_status=404
        ) from None
    error_code = audio_service._run_transcription(
        context.db, audio, content, audio.file_name
    )
    if error_code:
        raise AppError(error_code, audio.error or "音频转写失败，请重试")
    return {"transcript": audio.transcript or "", "transcribed": True}


def require_transcript_confirmation(context: AgentContext, inputs: dict) -> dict:
    record_id = inputs.get("record_id")
    if record_id:
        return {"transcript_confirmed": True}
    raise WaitForConfirmation(
        action_type="confirm_transcript",
        question="转写已完成，请先校对并确认转写，再生成纪要草稿。",
        payload={"audio_id": inputs.get("audio_id")},
    )


def generate_minutes_draft(context: AgentContext, inputs: dict) -> dict:
    meeting_id = str(inputs.get("meeting_id") or _require_meeting(context))
    payload = MinutesGenerateRequest(
        record_ids=[],
        include_action_items=False,
        include_materials=context.options.include_materials,
        template=None,
        template_id=context.options.template_id,
    )
    minutes = minutes_service.generate_minutes(
        context.db, meeting_id=meeting_id, user_id=context.user_id, payload=payload
    )
    return {
        "minutes_id": minutes.minutes_id,
        "minutes_content": minutes.content,
        "minutes_status": minutes.status,
        "minutes_version": minutes.version,
        "minutes_template": minutes.template,
    }


def extract_action_items_tool(context: AgentContext, inputs: dict) -> dict:
    meeting_id = str(inputs.get("meeting_id") or _require_meeting(context))
    items = action_item_service.extract_action_items(
        context.db, meeting_id=meeting_id, user_id=context.user_id, record_ids=[]
    )
    return {
        "action_items": [
            {
                "action_id": item.action_id,
                "content": item.content,
                "assignee": item.assignee,
                "due_date": item.due_date.isoformat() if item.due_date else None,
                "status": item.status,
            }
            for item in items
        ]
    }


def notify(context: AgentContext, inputs: dict) -> dict:  # noqa: ARG001
    minutes_id = inputs.get("minutes_id")
    count = len(inputs.get("action_items") or [])
    content = "已根据确认后的转写生成纪要草稿"
    if minutes_id:
        content += f"（{minutes_id}）"
    content += "，请在「纪要」标签中校对并确认。"
    if count:
        content += f" 同时提取了 {count} 个行动项草稿，需逐条确认后才能转为个人任务。"
    return {"content": content, "kind": "minutes", "minutes_id": minutes_id}


# ---------------------------------------------------------------- 注册表


TOOLS: dict[str, ToolSpec] = {
    "retrieve": ToolSpec("retrieve", retrieve, "检索会议材料与记录"),
    "answer_from_context": ToolSpec("answer_from_context", answer_from_context, "基于资料回答"),
    "ask_web_permission": ToolSpec(
        "ask_web_permission", ask_web_permission, "联网前请求用户确认", requires_confirmation=True
    ),
    "web_search": ToolSpec("web_search", web_search_tool, "联网检索"),
    "answer_with_web": ToolSpec("answer_with_web", answer_with_web, "基于联网结果回答"),
    "refuse": ToolSpec("refuse", refuse, "证据不足时拒答"),
    "prompt_task": ToolSpec(
        "prompt_task", prompt_task, "单次 LLM 文本处理（润色/精简/改写/翻译）"
    ),
    "load_audio": ToolSpec("load_audio", load_audio, "加载音频与转写状态"),
    "transcribe_audio": ToolSpec("transcribe_audio", transcribe_audio, "转写音频"),
    "require_transcript_confirmation": ToolSpec(
        "require_transcript_confirmation",
        require_transcript_confirmation,
        "转写确认门",
        requires_confirmation=True,
    ),
    "generate_minutes_draft": ToolSpec(
        "generate_minutes_draft", generate_minutes_draft, "生成纪要草稿（draft）"
    ),
    "extract_action_items": ToolSpec(
        "extract_action_items", extract_action_items_tool, "抽取行动项（待确认）"
    ),
    "notify": ToolSpec("notify", notify, "生成完成提示"),
}


def tool_functions() -> dict[str, Callable[[AgentContext, dict], dict]]:
    """供 `WorkflowRunner` 使用的 name → callable 映射。"""
    return {name: spec.run for name, spec in TOOLS.items()}


def get_tool(name: str) -> ToolSpec:
    spec = TOOLS.get(name)
    if spec is None:
        raise AppError("AGENT_TOOL_NOT_FOUND", f"工具未登记：{name}", http_status=500)
    return spec
