import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.preparation import PreparationDraft
from app.repositories import meeting_template_repository
from app.services import meeting_template_service, preparation_service

REGISTER = "/api/v1/auth/register"

PASSWORD = "secret123"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_templates_contains_builtin(client: TestClient) -> None:
    headers = _auth(client)
    response = client.get("/api/v1/meeting-templates", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]
    sources = {item["source"] for item in items}
    assert "builtin" in sources
    builtin_ids = {item["template_id"] for item in items if item["source"] == "builtin"}
    assert "tpl-builtin-standard-minutes" in builtin_ids
    for item in items:
        assert "content_text" not in item  # 列表不返回模板正文


def test_get_builtin_template_detail(client: TestClient) -> None:
    headers = _auth(client)
    response = client.get("/api/v1/meeting-templates/tpl-builtin-standard-minutes", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source"] == "builtin"
    assert data["content_text"]


def test_upload_list_and_delete_custom_template(client: TestClient) -> None:
    headers = _auth(client)
    response = client.post(
        "/api/v1/meeting-templates",
        data={"name": "产品评审模板", "description": "用于产品评审会"},
        files={"file": ("review.md", "# 目标\n# 结论\n# 待办".encode())},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    assert created["name"] == "产品评审模板"
    assert created["source"] == "custom"
    template_id = created["template_id"]

    listed = client.get("/api/v1/meeting-templates", headers=headers).json()["data"]
    assert any(item["template_id"] == template_id for item in listed)

    detail = client.get(f"/api/v1/meeting-templates/{template_id}", headers=headers)
    assert detail.status_code == 200
    assert "目标" in detail.json()["data"]["content_text"]

    deleted = client.delete(f"/api/v1/meeting-templates/{template_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    after = client.get(f"/api/v1/meeting-templates/{template_id}", headers=headers)
    assert after.status_code == 404


def test_upload_unsupported_type(client: TestClient) -> None:
    headers = _auth(client)
    response = client.post(
        "/api/v1/meeting-templates",
        files={"file": ("template.pdf", b"%PDF-1.4 fake")},
        headers=headers,
    )
    assert response.status_code == 415


def test_template_isolated_between_users(client: TestClient) -> None:
    owner = _auth(client, "owner")
    other = _auth(client, "other")
    created = client.post(
        "/api/v1/meeting-templates",
        files={"file": ("mine.txt", "私有模板结构".encode())},
        headers=owner,
    ).json()["data"]
    template_id = created["template_id"]

    assert client.get(f"/api/v1/meeting-templates/{template_id}", headers=other).status_code == 404
    assert (
        client.delete(f"/api/v1/meeting-templates/{template_id}", headers=other).status_code == 404
    )
    listed = client.get("/api/v1/meeting-templates", headers=other).json()["data"]
    assert all(item["template_id"] != template_id for item in listed)


def test_builtin_template_content_injected_into_prepare(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_generate(meeting, snippets, user_goal, config=None, **kwargs):
        captured["template_instructions"] = kwargs.get("template_instructions", "")
        return PreparationDraft(summary="摘要", checklist=[])

    monkeypatch.setattr(preparation_service, "generate_draft", fake_generate)
    headers = _auth(client)
    meeting = client.post(
        "/api/v1/meetings", json={"title": "评审会"}, headers=headers
    ).json()["data"]
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/prepare",
        json={"include_history": True, "template_id": "tpl-builtin-standard-minutes"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "议题" in str(captured["template_instructions"])


def test_custom_template_content_injected_into_prepare(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_generate(meeting, snippets, user_goal, config=None, **kwargs):
        captured["template_instructions"] = kwargs.get("template_instructions", "")
        return PreparationDraft(summary="摘要", checklist=[])

    monkeypatch.setattr(preparation_service, "generate_draft", fake_generate)
    headers = _auth(client)
    row = meeting_template_repository.create(
        db_session,
        template_id="tpl_custom_1",
        user_id=_user_id(db_session),
        name="我的模板",
        description=None,
        file_name="mine.txt",
        storage_key="templates/tpl_custom_1.txt",
        content_text="自定义结构要求",
    )
    assert row.template_id == "tpl_custom_1"
    meeting = client.post(
        "/api/v1/meetings", json={"title": "评审会"}, headers=headers
    ).json()["data"]
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/prepare",
        json={"include_history": True, "template_id": "tpl_custom_1"},
        headers=headers,
    )
    assert response.status_code == 200
    assert captured["template_instructions"] == "自定义结构要求"


def test_prepare_with_unknown_template_id(client: TestClient) -> None:
    headers = _auth(client)
    meeting = client.post(
        "/api/v1/meetings", json={"title": "评审会"}, headers=headers
    ).json()["data"]
    response = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/prepare",
        json={"include_history": True, "template_id": "tpl_missing"},
        headers=headers,
    )
    assert response.status_code == 404


def test_builtin_detail_for_other_users_without_ownership(client: TestClient) -> None:
    headers = _auth(client, "anyone")
    response = client.get(
        f"/api/v1/meeting-templates/{meeting_template_service.BUILTIN_TEMPLATES[0]['template_id']}",
        headers=headers,
    )
    assert response.status_code == 200


def _user_id(db_session: Session) -> str:
    from sqlalchemy import select

    from app.models.user import User

    return db_session.execute(select(User)).scalars().one().user_id
