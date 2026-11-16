"""本地工作区双向同步的服务端契约测试。

覆盖三块契约（`docs/api.md 一.3`、D-33）：
- 下载接口：材料/音频原始文件只按 id 提供，含跨用户与文件丢失；
- 幂等键：`client_op_id` 重复提交不产生重复记录，内容不同返回 409；
- 乐观锁：PATCH 携带 `expected_updated_at` / `expected_version`，不一致返回 409 `SYNC_CONFLICT`。
"""

from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.repositories import minutes_repository
from app.services import audio_service, material_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"
PASSWORD = "secret123"


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """材料与音频共用一个临时存储目录（下载接口读真实文件）。"""
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(material_service, "get_settings", fake_settings)
    monkeypatch.setattr(audio_service, "get_settings", fake_settings)
    monkeypatch.setattr(audio_service, "probe_duration_seconds", lambda *_: None)
    monkeypatch.setattr(
        audio_service,
        "transcribe_file",
        lambda content, file_name: "这是音频转写文本",
    )
    return tmp_path


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _meeting(client: TestClient, headers: dict[str, str], title: str = "同步会议") -> dict:
    response = client.post(MEETINGS, json={"title": title}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _upload_material(
    client: TestClient,
    headers: dict[str, str],
    meeting_id: str,
    *,
    name: str = "项目方案.txt",
    content: bytes = b"hello",
    client_op_id: str | None = None,
):
    data = {"client_op_id": client_op_id} if client_op_id else {}
    return client.post(
        f"/api/v1/meetings/{meeting_id}/materials",
        files={"file": (name, content, "text/plain")},
        data=data,
        headers=headers,
    )


def _upload_audio(
    client: TestClient,
    headers: dict[str, str],
    meeting_id: str,
    *,
    name: str = "会议录音.mp3",
    content: bytes = b"fake-audio",
    client_op_id: str | None = None,
):
    data = {"client_op_id": client_op_id} if client_op_id else {}
    return client.post(
        f"/api/v1/meetings/{meeting_id}/audio",
        files={"file": (name, content, "audio/mpeg")},
        data=data,
        headers=headers,
    )


# ============================ 下载接口 ============================


def test_material_download_roundtrip(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    payload = "内容".encode()
    uploaded = _upload_material(
        client, headers, meeting["meeting_id"], name="方案.txt", content=payload
    ).json()["data"]
    assert uploaded["file_size"] == len(payload)

    response = client.get(
        f"/api/v1/materials/{uploaded['material_id']}/download", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.content == payload
    disposition = response.headers["content-disposition"]
    assert "filename*=UTF-8''" in disposition
    # 中文文件名按 RFC 5987 百分号编码传输
    assert quote("方案.txt") in disposition


def test_material_download_cross_user_404(client: TestClient, media_root) -> None:
    headers = _auth(client, "alice")
    other = _auth(client, "bob")
    meeting = _meeting(client, headers)
    uploaded = _upload_material(client, headers, meeting["meeting_id"]).json()["data"]

    response = client.get(
        f"/api/v1/materials/{uploaded['material_id']}/download", headers=other
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_material_download_missing_file_404(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    uploaded = _upload_material(client, headers, meeting["meeting_id"]).json()["data"]

    for stored in media_root.rglob("*"):
        if stored.is_file():
            stored.unlink()

    response = client.get(
        f"/api/v1/materials/{uploaded['material_id']}/download", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_audio_download_roundtrip(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    uploaded = _upload_audio(client, headers, meeting["meeting_id"]).json()["data"]
    assert uploaded["file_size"] == len(b"fake-audio")

    response = client.get(
        f"/api/v1/audio/{uploaded['audio_id']}/download", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.content == b"fake-audio"


def test_audio_download_cross_user_404(client: TestClient, media_root) -> None:
    headers = _auth(client, "alice")
    other = _auth(client, "bob")
    meeting = _meeting(client, headers)
    uploaded = _upload_audio(client, headers, meeting["meeting_id"]).json()["data"]

    response = client.get(
        f"/api/v1/audio/{uploaded['audio_id']}/download", headers=other
    )
    assert response.status_code == 404


# ============================ 幂等键 ============================


def test_material_upload_idempotent(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    first = _upload_material(
        client, headers, meeting["meeting_id"], client_op_id="op-1"
    ).json()["data"]
    second = _upload_material(
        client, headers, meeting["meeting_id"], client_op_id="op-1"
    ).json()["data"]

    assert first["material_id"] == second["material_id"]
    listing = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/materials", headers=headers
    ).json()["data"]
    assert listing["pagination"]["total"] == 1


def test_material_upload_idempotency_key_reused_409(
    client: TestClient, media_root
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _upload_material(client, headers, meeting["meeting_id"], client_op_id="op-2")

    conflict = _upload_material(
        client, headers, meeting["meeting_id"], name="另一个文件.txt", client_op_id="op-2"
    )
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"


def test_record_create_idempotent(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    payload = {"content": "本地同步的记录", "client_op_id": "rec-op-1"}

    first = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/records", json=payload, headers=headers
    ).json()["data"]
    second = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/records", json=payload, headers=headers
    ).json()["data"]

    assert first["record_id"] == second["record_id"]


def test_issue_create_manual_and_idempotent(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    payload = {"description": "待澄清的口径", "follow_up": "下周确认", "client_op_id": "iss-op-1"}

    first = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/issues", json=payload, headers=headers
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["status"] == "open"

    second = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/issues", json=payload, headers=headers
    ).json()["data"]
    assert first.json()["data"]["issue_id"] == second["issue_id"]


def test_action_item_create_manual_pending_confirmation(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    payload = {
        "content": "整理会议纪要",
        "assignee": "张三",
        "due_date": "2026-11-12",
        "client_op_id": "act-op-1",
    }

    first = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/action-items",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201, first.text
    # 手工导入的行动项仍是候选，必须走确认/转任务，不落地为已完成
    assert first.json()["data"]["status"] == "pending_confirmation"

    second = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/action-items",
        json=payload,
        headers=headers,
    ).json()["data"]
    assert first.json()["data"]["action_id"] == second["action_id"]


# ============================ 乐观锁 ============================


def test_record_update_optimistic_lock_409(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/records",
        json={"content": "初版"},
        headers=headers,
    ).json()["data"]

    stale = client.patch(
        f"/api/v1/records/{record['record_id']}",
        json={"content": "本地修改", "expected_updated_at": "2020-01-01T00:00:00+00:00"},
        headers=headers,
    )
    assert stale.status_code == 409
    body = stale.json()
    assert body["error_code"] == "SYNC_CONFLICT"
    assert body["details"]["current_updated_at"]

    ok = client.patch(
        f"/api/v1/records/{record['record_id']}",
        json={"content": "本地修改", "expected_updated_at": record["updated_at"]},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["content"] == "本地修改"


def test_action_item_update_optimistic_lock_409(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    item = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/action-items",
        json={"content": "整理纪要", "client_op_id": "act-lock"},
        headers=headers,
    ).json()["data"]

    stale = client.patch(
        f"/api/v1/action-items/{item['action_id']}",
        json={"assignee": "李四", "expected_updated_at": "2020-01-01T00:00:00+00:00"},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error_code"] == "SYNC_CONFLICT"

    ok = client.patch(
        f"/api/v1/action-items/{item['action_id']}",
        json={"assignee": "李四", "expected_updated_at": item["updated_at"]},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["assignee"] == "李四"


def test_issue_update_optimistic_lock_409(client: TestClient) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    issue = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/issues",
        json={"description": "待澄清", "client_op_id": "iss-lock"},
        headers=headers,
    ).json()["data"]

    stale = client.patch(
        f"/api/v1/issues/{issue['issue_id']}",
        json={"follow_up": "本地补充", "expected_updated_at": "2020-01-01T00:00:00+00:00"},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error_code"] == "SYNC_CONFLICT"

    ok = client.patch(
        f"/api/v1/issues/{issue['issue_id']}",
        json={"follow_up": "本地补充", "expected_updated_at": issue["updated_at"]},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["follow_up"] == "本地补充"


def test_minutes_update_optimistic_lock_409(
    client: TestClient, db_session
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    minutes = minutes_repository.create(
        db_session,
        minutes_id="min_sync_test",
        meeting_id=meeting["meeting_id"],
        content="<p>纪要</p>",
        source_record_ids=[],
        source_material_ids=[],
        template="standard",
        status="confirmed",
    )
    current_version = minutes.version

    stale = client.patch(
        f"/api/v1/minutes/{minutes.minutes_id}",
        json={"content": "<p>本地修改</p>", "expected_version": current_version + 1},
        headers=headers,
    )
    assert stale.status_code == 409
    body = stale.json()
    assert body["error_code"] == "SYNC_CONFLICT"
    assert body["details"]["current_version"] == current_version

    ok = client.patch(
        f"/api/v1/minutes/{minutes.minutes_id}",
        json={"content": "<p>本地修改</p>", "expected_version": current_version},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["version"] == current_version + 1
