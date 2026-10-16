"""M10-02 权限与异常专项：越权统一 404、非法状态流转 409、AI 异常统一错误码。"""

import pytest
from fastapi.testclient import TestClient

from app.ai.extraction import ActionItemCandidate, IssueCandidate
from app.ai.preparation import PreparationDraft
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services import (
    action_item_service,
    issue_service,
    material_service,
    meeting_service,
    minutes_service,
    preparation_service,
)

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"
PASSWORD = "secret123"


@pytest.fixture()
def fake_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preparation_service,
        "generate_draft",
        lambda meeting, snippets, user_goal, config=None: PreparationDraft(
            summary="摘要", checklist=[]
        ),
    )
    monkeypatch.setattr(
        minutes_service, "generate_text", lambda meeting, records, config=None: "纪要"
    )
    monkeypatch.setattr(
        action_item_service,
        "extract_candidates",
        lambda records, config=None: [ActionItemCandidate(content="行动项")],
    )
    monkeypatch.setattr(
        issue_service,
        "extract_candidates",
        lambda records, config=None: [IssueCandidate(description="问题")],
    )


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(material_service, "get_settings", fake_settings)
    monkeypatch.setattr(meeting_service, "get_settings", fake_settings)
    return tmp_path


def _auth(client: TestClient, name: str) -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": name, "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_alice(client: TestClient, headers: dict[str, str]) -> dict[str, str]:
    meeting_id = client.post(MEETINGS, json={"title": "周会"}, headers=headers).json()["data"][
        "meeting_id"
    ]
    material_id = client.post(
        f"/api/v1/meetings/{meeting_id}/materials",
        files={"file": ("a.txt", b"x", "text/plain")},
        headers=headers,
    ).json()["data"]["material_id"]
    record_id = client.post(
        f"/api/v1/meetings/{meeting_id}/records", json={"content": "记录"}, headers=headers
    ).json()["data"]["record_id"]
    preparation_id = client.post(
        f"/api/v1/meetings/{meeting_id}/prepare", json={}, headers=headers
    ).json()["data"]["preparation_id"]
    minutes_id = client.post(
        f"/api/v1/meetings/{meeting_id}/minutes/generate",
        json={"record_ids": [record_id]},
        headers=headers,
    ).json()["data"]["minutes_id"]
    action_id = client.post(
        f"/api/v1/meetings/{meeting_id}/action-items/extract", json={}, headers=headers
    ).json()["data"]["items"][0]["action_id"]
    issue_id = client.post(
        f"/api/v1/meetings/{meeting_id}/issues/extract", json={}, headers=headers
    ).json()["data"]["items"][0]["issue_id"]
    client.post(f"/api/v1/action-items/{action_id}/confirm", headers=headers)
    task_id = client.post(
        f"/api/v1/action-items/{action_id}/convert-to-task",
        json={"title": "任务"},
        headers=headers,
    ).json()["data"]["task_id"]
    return {
        "meeting_id": meeting_id,
        "material_id": material_id,
        "record_id": record_id,
        "preparation_id": preparation_id,
        "minutes_id": minutes_id,
        "action_id": action_id,
        "issue_id": issue_id,
        "task_id": task_id,
    }


def test_unauthenticated_returns_auth_required(client: TestClient) -> None:
    response = client.get(MEETINGS)
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_cross_user_access_returns_404(
    client: TestClient, media_root, fake_ai: None
) -> None:
    alice = _auth(client, "alice")
    ids = _build_alice(client, alice)
    bob = _auth(client, "bob")

    meeting_id = ids["meeting_id"]
    checks = [
        client.get(f"{MEETINGS}/{meeting_id}", headers=bob),
        client.patch(f"{MEETINGS}/{meeting_id}", json={"title": "x"}, headers=bob),
        client.post(f"{MEETINGS}/{meeting_id}/archive", headers=bob),
        client.get(f"/api/v1/meetings/{meeting_id}/materials", headers=bob),
        client.get(f"/api/v1/materials/{ids['material_id']}", headers=bob),
        client.patch(f"/api/v1/records/{ids['record_id']}", json={"content": "x"}, headers=bob),
        client.patch(
            f"/api/v1/preparations/{ids['preparation_id']}",
            json={"summary": "x"},
            headers=bob,
        ),
        client.patch(f"/api/v1/minutes/{ids['minutes_id']}", json={"content": "x"}, headers=bob),
        client.patch(
            f"/api/v1/action-items/{ids['action_id']}", json={"content": "x"}, headers=bob
        ),
        client.patch(f"/api/v1/issues/{ids['issue_id']}", json={"status": "resolved"}, headers=bob),
        client.patch(f"/api/v1/tasks/{ids['task_id']}", json={"title": "x"}, headers=bob),
    ]
    for response in checks:
        assert response.status_code == 404, response.text
        assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_ai_timeout_propagates_error_code(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args, **kwargs):
        raise AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    monkeypatch.setattr(preparation_service, "generate_draft", timeout)
    monkeypatch.setattr(minutes_service, "generate_text", timeout)

    headers = _auth(client, "alice")
    meeting_id = client.post(MEETINGS, json={"title": "周会"}, headers=headers).json()["data"][
        "meeting_id"
    ]

    prepare = client.post(f"/api/v1/meetings/{meeting_id}/prepare", json={}, headers=headers)
    assert prepare.status_code == 504
    assert prepare.json()["error_code"] == "MODEL_TIMEOUT"
    assert prepare.json()["retryable"] is True

    minutes = client.post(
        f"/api/v1/meetings/{meeting_id}/minutes/generate", json={}, headers=headers
    )
    assert minutes.status_code == 504
    assert minutes.json()["error_code"] == "MODEL_TIMEOUT"


def test_illegal_state_transitions_return_409(
    client: TestClient, media_root, fake_ai: None
) -> None:
    headers = _auth(client, "alice")
    ids = _build_alice(client, headers)
    action_id = ids["action_id"]
    task_id = ids["task_id"]

    # 已转换的行动项不可删除
    deleted = client.delete(f"/api/v1/action-items/{action_id}", headers=headers)
    assert deleted.status_code == 409
    assert deleted.json()["error_code"] == "BUSINESS_RULE_VIOLATION"

    # 已完成任务不可取消
    client.patch(f"/api/v1/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    cancel = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=headers)
    assert cancel.status_code == 409

    # 已完成任务不可改回进行中
    reopen = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "in_progress"}, headers=headers
    )
    assert reopen.status_code == 409

    # 存在已转换行动项 → 会议不可删除
    delete_meeting = client.delete(f"{MEETINGS}/{ids['meeting_id']}", headers=headers)
    assert delete_meeting.status_code == 409
