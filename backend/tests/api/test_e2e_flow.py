"""M10-01 主闭环端到端：建会 → 资料 → 会前准备 → 记录/问答 → 纪要 → 行动项 → 任务。"""

import pytest
from fastapi.testclient import TestClient

from app.ai.chat import ChatAnswer
from app.ai.extraction import ActionItemCandidate
from app.ai.preparation import PreparationDraft
from app.core.config import get_settings
from app.services import (
    action_item_service,
    ai_chat_service,
    material_service,
    meeting_service,
    minutes_service,
    preparation_service,
)

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"
PASSWORD = "secret123"


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(material_service, "get_settings", fake_settings)
    monkeypatch.setattr(meeting_service, "get_settings", fake_settings)
    return tmp_path


@pytest.fixture()
def fake_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preparation_service,
        "generate_draft",
        lambda meeting, snippets, user_goal, config=None, **kwargs: PreparationDraft(
            summary="会前摘要", checklist=["确认里程碑", "排查风险"]
        ),
    )
    monkeypatch.setattr(
        minutes_service,
        "generate_text",
        lambda meeting, transcripts, config=None, **kwargs: "会议纪要正文",
    )
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda transcripts, config=None: [
            ActionItemCandidate(content="完成接口联调", assignee="张三")
        ],
    )

    class _InsufficientChat:
        def answer(self, question, *, user_id, scope, current_meeting_id, records=None, **kwargs):
            return ChatAnswer(answer="无法确认", sources=[], insufficient_evidence=True)

    monkeypatch.setattr(
        ai_chat_service, "_chat_service", lambda db, user_id: _InsufficientChat()
    )


def _auth(client: TestClient) -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": "alice", "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_mvp_closed_loop(
    client: TestClient, media_root, fake_ai: None
) -> None:
    headers = _auth(client)

    # 1) 创建会议
    meeting = client.post(
        MEETINGS, json={"title": "项目周会", "topic": "进度与风险"}, headers=headers
    )
    assert meeting.status_code == 201
    meeting_id = meeting.json()["data"]["meeting_id"]

    # 2) 上传资料
    upload = client.post(
        f"/api/v1/meetings/{meeting_id}/materials",
        files={"file": ("项目方案.txt", b"plan-content", "text/plain")},
        data={"source": "会前材料"},
        headers=headers,
    )
    assert upload.status_code == 201
    assert upload.json()["data"]["processing_status"] == "processed"

    # 3) 会前准备
    prep = client.post(f"/api/v1/meetings/{meeting_id}/prepare", json={}, headers=headers)
    assert prep.status_code == 200
    prep_data = prep.json()["data"]
    assert prep_data["status"] == "draft"
    assert prep_data["checklist"] == ["确认里程碑", "排查风险"]

    # 4) 会中记录
    record = client.post(
        f"/api/v1/meetings/{meeting_id}/records",
        json={"content": "讨论了接口联调计划"},
        headers=headers,
    )
    assert record.status_code == 201
    record_id = record.json()["data"]["record_id"]

    # 5) 问答（AI 已 mock，无真实检索 → 证据不足，不伪造来源）
    chat = client.post(
        f"/api/v1/meetings/{meeting_id}/chat",
        json={"question": "上次会议决定了什么？"},
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["data"]["insufficient_evidence"] is True
    assert chat.json()["data"]["sources"] == []

    # 6) 生成纪要并确认
    minutes = client.post(
        f"/api/v1/meetings/{meeting_id}/minutes/generate",
        json={"record_ids": [record_id]},
        headers=headers,
    )
    assert minutes.status_code == 201
    minutes_id = minutes.json()["data"]["minutes_id"]
    assert minutes.json()["data"]["status"] == "draft"
    confirmed = client.post(f"/api/v1/minutes/{minutes_id}/confirm", headers=headers)
    assert confirmed.json()["data"]["status"] == "confirmed"

    # 7) 提取行动项 → 确认 → 转任务
    extract = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/extract",
        json={"record_ids": [record_id]},
        headers=headers,
    )
    assert extract.status_code == 200
    action_id = extract.json()["data"]["items"][0]["action_id"]
    client.post(f"/api/v1/action-items/{action_id}/confirm", headers=headers)
    convert = client.post(
        f"/api/v1/action-items/{action_id}/convert-to-task",
        json={"title": "完成接口联调"},
        headers=headers,
    )
    assert convert.status_code == 201
    task_id = convert.json()["data"]["task_id"]
    assert convert.json()["data"]["action_id"] == action_id

    # 8) 任务跟进
    tasks = client.get("/api/v1/tasks", headers=headers).json()["data"]
    assert tasks["pagination"]["total"] == 1
    started = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "in_progress"}, headers=headers
    )
    assert started.json()["data"]["status"] == "in_progress"
    done = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "completed"}, headers=headers
    )
    assert done.json()["data"]["status"] == "completed"

    # 9) 存在已转换行动项 → 会议不可删除
    delete = client.delete(f"{MEETINGS}/{meeting_id}", headers=headers)
    assert delete.status_code == 409
    assert delete.json()["error_code"] == "BUSINESS_RULE_VIOLATION"
