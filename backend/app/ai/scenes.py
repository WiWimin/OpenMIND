"""AI 调用场景（scene）注册表：场景 → 用途（purpose）+ 生成参数 + 输入上限。

集中原本散落在各调用点的魔数（`relevance.py` 的 `temperature=0/max_tokens=16`、
模板草稿的 `temperature=0.4`、各服务硬编码的 `ModelPurpose.*`），保证：

- **用途路由**：`scene_purpose()` 供 `resolve_model_config(purpose=...)` 使用，
  场景与 BYOK 用途模型（`llm_purpose_models`）一一对应；
- **生成参数**：`scene_params()` 返回温度/输出上限/超时，调用方未显式覆盖时取此值；
- **输入预检**：`input_token_limit` 供 `ai/tokens.py` 按场景限制输入长度
 （`None` 表示用全局 `AI_INPUT_TOKEN_LIMIT`）。

场景名与 `ai/structured.py` 的 `scene` 参数、`docs/ai-design.md 3.3` 保持一致。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.model_config import ModelPurpose


@dataclass(frozen=True)
class SceneSpec:
    """单个场景的调用参数。"""

    name: str
    # BYOK 用途模型路由；None = 不做用途覆盖（用默认模型）
    purpose: ModelPurpose | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_s: float = 60.0
    # 输入 token 预检上限；None = 全局 AI_INPUT_TOKEN_LIMIT
    input_token_limit: int | None = None


# 场景注册表：键与 run_structured(scene=...) / 服务调用点一致
SCENES: dict[str, SceneSpec] = {
    # 会前准备（purpose=preparation 用途模型）
    "prepare": SceneSpec("prepare", purpose=ModelPurpose.preparation),
    # 会议问答（普通回答 + build 可交付文件）
    "chat": SceneSpec("chat", purpose=ModelPurpose.chat),
    "chat_build": SceneSpec("chat_build", purpose=ModelPurpose.chat),
    # 记录整理（summary/polish 走结构化管线，其余直出）
    "organize": SceneSpec("organize", purpose=ModelPurpose.chat),
    "organize_summary": SceneSpec("organize_summary", purpose=ModelPurpose.chat),
    "organize_polish": SceneSpec("organize_polish", purpose=ModelPurpose.chat),
    # 纪要生成（长输入：全文转写 + 材料，放宽到 60k token）
    "minutes": SceneSpec(
        "minutes", purpose=ModelPurpose.minutes, timeout_s=120.0, input_token_limit=60_000
    ),
    # 行动项 / 问题提取（purpose=extraction 用途模型）
    "extract_action_items": SceneSpec(
        "extract_action_items", purpose=ModelPurpose.extraction
    ),
    "extract_issues": SceneSpec("extract_issues", purpose=ModelPurpose.extraction),
    # 模板草稿生成：创造性任务，温度更高
    "template_draft": SceneSpec(
        "template_draft", purpose=ModelPurpose.minutes, temperature=0.4
    ),
    # RAG 相关性 Judge：确定性判定，温度 0 + 小输出；输入为问题 + 3 段摘录
    "rag_judge": SceneSpec(
        "rag_judge",
        temperature=0.0,
        max_tokens=16,
        timeout_s=30.0,
        input_token_limit=4_000,
    ),
    # Agent 意图路由：确定性分类，温度 0 + 小输出 + 短超时；
    # 失败/超时由调用方回退规则层，绝不阻断对话。
    # `timeout_s` 仅为兜底默认值，实际调用点用 AGENT_INTENT_LLM_TIMEOUT_S 覆盖
    "intent_router": SceneSpec(
        "intent_router",
        purpose=ModelPurpose.chat,
        temperature=0.0,
        max_tokens=200,
        timeout_s=3.0,
        input_token_limit=4_000,
    ),
}

_DEFAULT_SCENE = SceneSpec("default")


def get_scene(name: str | None) -> SceneSpec:
    """按名取场景；未登记/空名返回默认场景（温度 0.2、无上限）。"""
    if not name:
        return _DEFAULT_SCENE
    return SCENES.get(name, _DEFAULT_SCENE)


def scene_purpose(name: str | None) -> ModelPurpose | None:
    """场景对应的 BYOK 用途；未登记场景不做用途覆盖。"""
    return SCENES[name].purpose if name in SCENES else None
