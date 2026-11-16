"""会前速览契约：长度收口与提示词边界。"""

from __future__ import annotations

from app.ai.brief import BriefMaterial, MaterialBriefService
from app.ai.prompts import build_brief
from app.schemas.chat import MaterialBrief


class _StubLLM:
    """结构化输出替身：直接返回已校验对象，记录收到的消息。"""

    def __init__(self, brief: MaterialBrief) -> None:
        self.brief = brief
        self.calls: list[tuple[list[dict[str, str]], type, str]] = []

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: type,
        scene: str,
    ) -> MaterialBrief:
        self.calls.append((messages, schema, scene))
        return self.brief


def test_material_brief_clips_overlong_fields() -> None:
    brief = MaterialBrief(
        headline="这是一句明显超过四十个字上限的会议核心问题描述，用来验证截断逻辑是否生效并保留省略号",
        key_points=[f"第 {index} 条要点" + "很长的补充说明" * 6 for index in range(8)],
        decisions_needed=["需要确认的事项" * 5 for _ in range(5)],
        risks=["风险描述" * 8 for _ in range(4)],
        next_step="会前需要完成的一件很具体的事情，但这句话也超过了四十个字的上限",
    )

    assert len(brief.headline) <= 40
    assert len(brief.key_points) <= 5
    assert all(len(item) <= 40 for item in brief.key_points)
    assert len(brief.decisions_needed) <= 3
    assert all(len(item) <= 30 for item in brief.decisions_needed)
    assert len(brief.risks) <= 2
    assert all(len(item) <= 30 for item in brief.risks)
    assert len(brief.next_step) <= 40

    total = (
        len(brief.headline)
        + sum(len(item) for item in brief.key_points)
        + sum(len(item) for item in brief.decisions_needed)
        + sum(len(item) for item in brief.risks)
        + len(brief.next_step)
    )
    assert total <= 300


def test_material_brief_drops_blank_items() -> None:
    brief = MaterialBrief(
        headline="季度预算评审",
        key_points=["  ", "预算缺口 20 万", ""],
        decisions_needed=[],
        risks=[],
        next_step="",
    )

    assert brief.key_points == ["预算缺口 20 万"]


def test_build_brief_prompt_forbids_checklist_and_requires_grounding() -> None:
    messages = build_brief(
        {
            "meeting_topic": "季度预算评审",
            "material_snippets": ["【预算表】差旅预算超支"],
            "user_goal": "关注超支原因",
        }
    )

    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "不超过 300 字" in system
    assert "准备清单" in system
    assert "禁止臆造" in system
    assert "季度预算评审" in user
    assert "差旅预算超支" in user
    assert "关注超支原因" in user


def test_brief_service_sends_materials_and_user_goal_to_model() -> None:
    stub = _StubLLM(
        MaterialBrief(
            headline="评审季度预算",
            key_points=["差旅预算超支 20 万"],
            decisions_needed=[],
            risks=[],
            next_step="确认超支原因",
        )
    )

    brief = MaterialBriefService(stub).generate(
        meeting_topic="季度预算评审",
        materials=[
            BriefMaterial(
                material_id="mat_1",
                name="预算表.txt",
                content="差旅预算超支 20 万",
            )
        ],
        user_goal="关注超支原因",
    )

    assert brief.headline == "评审季度预算"
    messages, schema, scene = stub.calls[0]
    assert schema is MaterialBrief
    assert scene == "brief"
    assert "预算表.txt" in messages[1]["content"]
    assert "差旅预算超支 20 万" in messages[1]["content"]
    assert "关注超支原因" in messages[1]["content"]


def test_brief_service_skips_blank_material_content() -> None:
    stub = _StubLLM(MaterialBrief(headline="暂无资料"))

    MaterialBriefService(stub).generate(
        meeting_topic="周会",
        materials=[BriefMaterial(material_id=None, name=None, content="   ")],
    )

    messages = stub.calls[0][0]
    # 空白资料不进提示词，模型只能看到「暂无资料」
    assert "（暂无资料）" in messages[1]["content"]
