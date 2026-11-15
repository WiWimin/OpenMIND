"""后端意图路由：显式覆盖 → 规则 → LLM 兜底 → 安全回退。

设计目标（`docs/agent-framework.md 3.1`）：

- 规则层覆盖高频表达，命中即返回（p95 < 50ms，不产生模型调用）；
- 规则未命中且开关开启时，才走一次确定性 LLM 分类（温度 0、3s 超时）；
- LLM 失败/超时/输出非法一律回退 `chat`，绝不阻断对话；
- 页面场景只作为弱先验，同一句话在不同页面得到同一意图（仅澄清文案不同）。
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.ai.prompts import build_intent
from app.ai.structured import run_structured
from app.core.config import get_settings
from app.schemas.agent import AgentIntent, AgentIntentDecision, AgentScene
from app.services import ai_audit_service
from app.services.model_config_service import (
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)

logger = logging.getLogger(__name__)

# 规则顺序即优先级：更具体的意图放前面，避免被宽泛关键词抢占
_RULES: tuple[tuple[AgentIntent, re.Pattern[str]], ...] = (
    (
        AgentIntent.minutes_generate,
        re.compile(r"会议纪要|生成纪要|写纪要|纪要草稿|纪要"),
    ),
    (
        AgentIntent.action_items_extract,
        re.compile(r"待办|行动项|任务清单|提取任务|拆分任务"),
    ),
    (
        AgentIntent.issues_extract,
        re.compile(r"未解决问题|待确认事项|风险点|问题清单|遗留问题"),
    ),
    (
        # 会前速览：只读本场资料的摘要卡，必须排在 prepare 之前；
        # 负向断言避免「会前准备摘要」这类旧表述被误判为速览。
        AgentIntent.brief,
        re.compile(r"(?<!准备)摘要|速览|总结一下|概括一下|总结资料|概括资料|资料总结"),
    ),
    (
        AgentIntent.prepare,
        re.compile(r"会前准备|准备稿|准备清单|生成准备"),
    ),
    (
        AgentIntent.organize,
        re.compile(r"整理记录|整理会议记录|整理一下|整理稿|去口语|润色|精简记录"),
    ),
    (
        AgentIntent.knowledge_search,
        re.compile(r"个人知识库|我的知识库|知识库检索|查我的资料"),
    ),
    (
        AgentIntent.build_file,
        re.compile(r"生成文件|导出文件|写成文档|可交付|build\s*模式", re.IGNORECASE),
    ),
    (
        AgentIntent.web_search,
        re.compile(r"联网|上网查|搜索一下|外部资料|最新消息|网上"),
    ),
    (
        AgentIntent.transcribe,
        re.compile(r"转写|录音转文字|识别音频|语音转文字"),
    ),
    (
        AgentIntent.help,
        re.compile(r"你能做什么|怎么用|使用说明|帮助|help", re.IGNORECASE),
    ),
    (
        AgentIntent.clarify,
        re.compile(r"^帮我(处理|看看|弄)一下[。！!]?$|^处理一下[。！!]?$"),
    ),
)

# 页面弱先验：只影响澄清文案与低置信兜底，不覆盖明确规则
_CLARIFY_BY_SCENE: dict[str, str] = {
    AgentScene.preprocess.value: "你是想生成会前准备、检索资料，还是直接提问？",
    AgentScene.asr.value: "你是想提问、转写录音，还是生成纪要？",
    AgentScene.minutes.value: "你是想生成纪要、整理记录，还是提取行动项？",
}

_INTENT_VALUES = {intent.value for intent in AgentIntent}


def _rule_decision(message: str, scene: str) -> AgentIntentDecision | None:
    text = message.strip()
    if not text:
        return None
    matches: list[AgentIntent] = []
    for intent, pattern in _RULES:
        if pattern.search(text):
            matches.append(intent)
    if not matches:
        return None
    # 多规则冲突：取优先级最高者，但降低置信度交给 LLM 复核
    intent = matches[0]
    confidence = 0.92 if len(matches) == 1 else 0.62
    decision = AgentIntentDecision(
        intent=intent,
        confidence=confidence,
        source="rule",
    )
    if intent is AgentIntent.clarify:
        decision.needs_clarification = True
        decision.clarification_question = _CLARIFY_BY_SCENE.get(
            scene, "能再具体说明一下你想做什么吗？"
        )
    return decision


def _llm_decision(
    db: Session, *, user_id: str, message: str, scene: str, meeting_state: str
) -> AgentIntentDecision | None:
    settings = get_settings()
    if not settings.agent_intent_llm_enabled:
        return None
    try:
        config = resolve_model_config(
            db, user_id, purpose=ModelPurpose.chat
        )
        client = build_llm_client(config)
        with ai_audit_service.audit_call(
            db,
            user_id=user_id,
            scene="intent_router",
            model=config.llm_model,
            provider="",
        ):
            decision = run_structured(
                lambda messages: client.chat_json(
                    messages,
                    schema=AgentIntentDecision,
                    scene="intent_router",
                    # 配置覆盖场景默认超时；路由是对话前置，必须快进快出
                    timeout_s=settings.agent_intent_llm_timeout_s,
                ),
                build_intent(
                    {
                        "message": message,
                        "scene": scene,
                        "meeting_state": meeting_state,
                    }
                ),
                AgentIntentDecision,
                scene="intent_router",
                on_failure="degrade",
            )
    except Exception as exc:  # noqa: BLE001 — 路由失败绝不阻断对话
        logger.warning("意图路由 LLM 兜底失败，回退 chat：%s", type(exc).__name__)
        return None
    if decision is None or decision.intent.value not in _INTENT_VALUES:
        return None
    decision.source = "llm"
    decision.confidence = max(0.0, min(1.0, decision.confidence))
    if decision.needs_clarification and not decision.clarification_question:
        decision.clarification_question = _CLARIFY_BY_SCENE.get(
            scene, "能再具体说明一下你想做什么吗？"
        )
    # 低置信度但模型给出明确意图时仍采用，避免无意义澄清
    return decision


def classify(
    db: Session,
    *,
    user_id: str,
    message: str,
    scene: str = AgentScene.minutes.value,
    meeting_state: str = "",
    explicit: AgentIntent | None = None,
) -> AgentIntentDecision:
    """三级路由入口：显式 → 规则 → LLM → 回退 chat。"""
    if explicit is not None:
        return AgentIntentDecision(intent=explicit, confidence=1.0, source="explicit")

    rule = _rule_decision(message, scene)
    if rule is not None and rule.confidence >= 0.8:
        return rule

    llm = _llm_decision(
        db, user_id=user_id, message=message, scene=scene, meeting_state=meeting_state
    )
    if llm is not None:
        return llm

    if rule is not None:
        return rule

    # 规则与 LLM 均未命中：普通对话是最安全的默认
    return AgentIntentDecision(intent=AgentIntent.chat, confidence=0.4, source="fallback")
