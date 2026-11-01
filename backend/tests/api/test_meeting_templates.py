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
    assert "tpl-builtin-minutes" in builtin_ids
    assert "tpl-builtin-pre-summary" in builtin_ids
    for item in items:
        assert "content_text" not in item  # 列表不返回模板正文
        assert item["content_preview"]  # 但返回卡片缩略图用的内容预览
        assert item["category"] in ("会前", "会后", "通用")


def test_get_builtin_template_detail(client: TestClient) -> None:
    headers = _auth(client)
    response = client.get("/api/v1/meeting-templates/tpl-builtin-minutes", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source"] == "builtin"
    assert data["category"] == "会后"
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
        json={"include_history": True, "template_id": "tpl-builtin-minutes"},
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


def test_create_text_template(client: TestClient) -> None:
    headers = _auth(client)
    response = client.post(
        "/api/v1/meeting-templates/text",
        json={
            "name": "评审会纪要",
            "description": "用于评审会",
            "category": "会后",
            "content_text": "1. 评审结论；2. 问题清单；3. 待办。",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    assert created["source"] == "custom"
    assert created["category"] == "会后"
    assert created["file_name"] is None
    assert created["content_preview"].startswith("1. 评审结论")

    detail = client.get(f"/api/v1/meeting-templates/{created['template_id']}", headers=headers)
    assert detail.status_code == 200
    assert "评审结论" in detail.json()["data"]["content_text"]


def test_create_text_template_validations(client: TestClient) -> None:
    headers = _auth(client)
    empty = client.post(
        "/api/v1/meeting-templates/text",
        json={"name": "空白模板", "content_text": "   "},
        headers=headers,
    )
    assert empty.status_code == 422

    bad_category = client.post(
        "/api/v1/meeting-templates/text",
        json={"name": "分类错误", "category": "会中", "content_text": "内容"},
        headers=headers,
    )
    assert bad_category.status_code == 422


def test_duplicate_template_via_text_create(client: TestClient) -> None:
    """另存为 = 读取详情后按文本创建副本。"""
    headers = _auth(client)
    source = client.post(
        "/api/v1/meeting-templates/text",
        json={"name": "原始模板", "category": "通用", "content_text": "1. 结构要点"},
        headers=headers,
    ).json()["data"]
    detail = client.get(f"/api/v1/meeting-templates/{source['template_id']}", headers=headers)

    copied = client.post(
        "/api/v1/meeting-templates/text",
        json={
            "name": "原始模板 副本",
            "category": detail.json()["data"]["category"],
            "content_text": detail.json()["data"]["content_text"],
        },
        headers=headers,
    )
    assert copied.status_code == 201
    assert copied.json()["data"]["template_id"] != source["template_id"]


def test_generate_template_draft(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeDraft:
        name = "周会复盘"
        description = "适用于每周例会的复盘结构"
        category = "会后"
        content_text = "1. 数据回顾；2. 风险与阻塞；3. 改进项。"

    class FakeClient:
        def chat_json(self, *args, **kwargs):
            return FakeDraft()

    monkeypatch.setattr(
        meeting_template_service, "build_llm_client", lambda config: FakeClient()
    )
    headers = _auth(client)
    response = client.post(
        "/api/v1/meeting-templates/generate",
        json={"description": "每周例会的复盘模板"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["name"] == "周会复盘"
    assert data["category"] == "会后"
    assert "数据回顾" in data["content_text"]
    # 草稿不入库
    listed = client.get("/api/v1/meeting-templates", headers=headers).json()["data"]
    assert all(item["name"] != "周会复盘" for item in listed)


def test_generate_template_requires_configured_llm(client: TestClient) -> None:
    headers = _auth(client)
    response = client.post(
        "/api/v1/meeting-templates/generate",
        json={"description": "周会模板"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_REQUIRED"


def _user_id(db_session: Session) -> str:
    from sqlalchemy import select

    from app.models.user import User

    return db_session.execute(select(User)).scalars().one().user_id
