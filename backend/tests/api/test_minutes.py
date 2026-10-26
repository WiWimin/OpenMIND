import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import action_item_service, material_service, minutes_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "周会"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _record(
    client: TestClient,
    headers: dict[str, str],
    meeting_id: str,
    content: str = "讨论记录",
    marker_type: str | None = None,
) -> dict:
    body: dict = {"content": content}
    if marker_type is not None:
        body["marker_type"] = marker_type
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/records",
        json=body,
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _material(client: TestClient, headers: dict[str, str], meeting_id: str) -> dict:
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/materials",
        files={"file": ("plan.txt", "项目计划：周五上线".encode(), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _generate(client: TestClient, headers: dict[str, str], meeting_id: str, **extra):
    payload = {"record_ids": [], "include_action_items": False}
    payload.update(extra)
    return client.post(
        f"/api/v1/meetings/{meeting_id}/minutes/generate", json=payload, headers=headers
    )


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(material_service, "get_settings", fake_settings)
    return tmp_path


@pytest.fixture()
def fake_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        minutes_service,
        "generate_text",
        lambda meeting, transcripts, config=None, **kwargs: "会议纪要正文",
    )


def test_generate_minutes(client: TestClient, fake_minutes: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])

    response = _generate(client, headers, meeting["meeting_id"], record_ids=[record["record_id"]])
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["minutes_id"].startswith("min_")
    assert data["content"] == "会议纪要正文"
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert data["source_record_ids"] == [record["record_id"]]
    assert data["source_material_ids"] == []
    assert data["template"] == "standard"


def test_generate_accepts_template(
    client: TestClient, fake_minutes: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _generate(
        client, headers, meeting["meeting_id"], template="concise"
    )

    assert response.status_code == 201
    assert response.json()["data"]["template"] == "concise"


def test_generate_rejects_unknown_template(
    client: TestClient, fake_minutes: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)

    response = _generate(
        client, headers, meeting["meeting_id"], template="unknown"
    )

    assert response.status_code == 422


def test_generate_fuses_materials_and_marked_records(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def capture(meeting, transcripts, config=None, **kwargs):
        captured.update(kwargs)
        return "融合纪要"

    monkeypatch.setattr(minutes_service, "generate_text", capture)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    material = _material(client, headers, meeting["meeting_id"])
    decision = _record(
        client,
        headers,
        meeting["meeting_id"],
        content="决定周五上线",
        marker_type="decision",
    )
    ordinary = _record(client, headers, meeting["meeting_id"], content="讨论排期")

    response = _generate(
        client,
        headers,
        meeting["meeting_id"],
        record_ids=[decision["record_id"], ordinary["record_id"]],
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["source_record_ids"] == [
        decision["record_id"],
        ordinary["record_id"],
    ]
    assert data["source_material_ids"] == [material["material_id"]]
    assert captured["material_snippets"] == ["项目计划：周五上线"]
    assert captured["marked_records"] == [
        {
            "record_id": decision["record_id"],
            "marker_type": "decision",
            "content": "决定周五上线",
        }
    ]


def test_generate_can_exclude_materials(
    client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def capture(meeting, transcripts, config=None, **kwargs):
        captured.update(kwargs)
        return "仅记录纪要"

    monkeypatch.setattr(minutes_service, "generate_text", capture)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _material(client, headers, meeting["meeting_id"])
    record = _record(client, headers, meeting["meeting_id"])

    response = _generate(
        client,
        headers,
        meeting["meeting_id"],
        record_ids=[record["record_id"]],
        include_materials=False,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["source_material_ids"] == []
    assert captured["material_snippets"] == []


def test_generate_requires_auth(client: TestClient, fake_minutes: None) -> None:
    response = client.post("/api/v1/meetings/mtg_x/minutes/generate", json={})
    assert response.status_code == 401


def test_generate_meeting_not_found(client: TestClient, fake_minutes: None) -> None:
    response = _generate(client, _auth(client), "mtg_missing")
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_generate_cross_user_forbidden(client: TestClient, fake_minutes: None) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    bob = _auth(client, "bob")
    assert _generate(client, bob, meeting["meeting_id"]).status_code == 404


def test_generate_ai_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.exceptions import AppError

    def boom(meeting, transcripts, config=None, **kwargs):
        raise AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    monkeypatch.setattr(minutes_service, "generate_text", boom)
    headers = _auth(client)
    meeting = _meeting(client, headers)
    response = _generate(client, headers, meeting["meeting_id"])
    assert response.status_code == 504
    assert response.json()["error_code"] == "MODEL_TIMEOUT"


def test_list_minutes(client: TestClient, fake_minutes: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    _generate(client, headers, meeting["meeting_id"])
    _generate(client, headers, meeting["meeting_id"])

    response = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/minutes", headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pagination"]["total"] == 2
    assert len(data["items"]) == 2


def test_get_and_cross_user(client: TestClient, fake_minutes: None) -> None:
    alice = _auth(client, "alice")
    meeting = _meeting(client, alice)
    minutes = _generate(client, alice, meeting["meeting_id"]).json()["data"]
    url = f"/api/v1/minutes/{minutes['minutes_id']}"

    found = client.get(url, headers=alice)
    assert found.status_code == 200
    assert found.json()["data"]["minutes_id"] == minutes["minutes_id"]

    bob = _auth(client, "bob")
    assert client.get(url, headers=bob).status_code == 404


def test_update_minutes_increments_version(client: TestClient, fake_minutes: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    minutes = _generate(client, headers, meeting["meeting_id"]).json()["data"]

    response = client.patch(
        f"/api/v1/minutes/{minutes['minutes_id']}",
        json={"content": "修改后的纪要"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content"] == "修改后的纪要"
    assert data["version"] == 2


def test_regeneration_does_not_overwrite_confirmed_minutes(
    client: TestClient, fake_minutes: None
) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    original = _generate(client, headers, meeting["meeting_id"]).json()["data"]
    confirmed = client.post(
        f"/api/v1/minutes/{original['minutes_id']}/confirm", headers=headers
    ).json()["data"]

    regenerated = _generate(
        client, headers, meeting["meeting_id"], template="concise"
    ).json()["data"]
    current = client.get(
        f"/api/v1/minutes/{original['minutes_id']}", headers=headers
    ).json()["data"]

    assert regenerated["minutes_id"] != confirmed["minutes_id"]
    assert regenerated["template"] == "concise"
    assert current["content"] == confirmed["content"]
    assert current["status"] == "confirmed"
    assert current["version"] == confirmed["version"]


def test_confirm_minutes(client: TestClient, fake_minutes: None) -> None:
    headers = _auth(client)
    meeting = _meeting(client, headers)
    minutes = _generate(client, headers, meeting["meeting_id"]).json()["data"]
    url = f"/api/v1/minutes/{minutes['minutes_id']}/confirm"

    first = client.post(url, headers=headers)
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "confirmed"

    second = client.post(url, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "confirmed"


def test_generate_include_action_items(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ai.extraction import ActionItemCandidate

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
    headers = _auth(client)
    meeting = _meeting(client, headers)
    record = _record(client, headers, meeting["meeting_id"])

    response = _generate(
        client,
        headers,
        meeting["meeting_id"],
        record_ids=[record["record_id"]],
        include_action_items=True,
    )
    assert response.status_code == 201

    listing = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/action-items", headers=headers
    ).json()["data"]
    assert listing["pagination"]["total"] == 1
    assert listing["items"][0]["content"] == "完成接口联调"
    assert listing["items"][0]["status"] == "pending_confirmation"
