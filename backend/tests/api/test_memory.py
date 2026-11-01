from fastapi.testclient import TestClient

from app.services import minutes_service

PATH = "/api/v1/me/memory"
REGISTER = "/api/v1/auth/register"
PASSWORD = "secret123"


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": name, "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_empty_memory(client: TestClient) -> None:
    response = client.get(PATH, headers=_auth(client))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "role": "",
        "work_scenarios": "",
        "communication_style": "",
        "preferred_minutes_template": None,
        "updated_at": None,
    }


def test_put_and_get_memory(client: TestClient) -> None:
    headers = _auth(client)
    payload = {
        "role": "产品经理",
        "work_scenarios": "B2B SaaS 产品规划",
        "communication_style": "简洁、结论先行",
        "preferred_minutes_template": "concise",
    }

    saved = client.put(PATH, json=payload, headers=headers)

    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["role"] == "产品经理"
    assert data["preferred_minutes_template"] == "concise"
    assert data["updated_at"] is not None

    got = client.get(PATH, headers=headers).json()["data"]
    assert got["work_scenarios"] == "B2B SaaS 产品规划"
    assert got["communication_style"] == "简洁、结论先行"


def test_invalid_preferred_template_rejected(client: TestClient) -> None:
    response = client.put(
        PATH,
        json={"preferred_minutes_template": "unknown"},
        headers=_auth(client),
    )

    assert response.status_code == 422


def test_memory_isolated_between_users(client: TestClient) -> None:
    alice = _auth(client, "alice")
    bob = _auth(client, "bob")
    client.put(PATH, json={"role": "Alice 的角色"}, headers=alice)

    bob_memory = client.get(PATH, headers=bob).json()["data"]

    assert bob_memory["role"] == ""


def test_delete_memory(client: TestClient) -> None:
    headers = _auth(client)
    client.put(PATH, json={"role": "产品经理"}, headers=headers)

    deleted = client.delete(PATH, headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"deleted": True}
    assert client.get(PATH, headers=headers).json()["data"]["role"] == ""


def test_minutes_uses_preferred_template_when_not_explicit(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        minutes_service,
        "generate_text",
        lambda *args, **kwargs: "纪要",
    )
    headers = _auth(client)
    client.put(
        PATH,
        json={"preferred_minutes_template": "task_list"},
        headers=headers,
    )
    meeting = client.post(
        "/api/v1/meetings", json={"title": "周会"}, headers=headers
    ).json()["data"]

    generated = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/minutes/generate",
        json={"record_ids": []},
        headers=headers,
    )

    assert generated.status_code == 201
    assert generated.json()["data"]["template"] == "task_list"


def test_minutes_uses_template_id_as_preferred(
    client: TestClient, db_session, monkeypatch
) -> None:
    """默认模板也可以指向模板清单中的模板 id（内置或自定义）。"""
    captured: dict[str, object] = {}

    def fake_generate(*args, **kwargs):
        captured["template_instructions"] = kwargs.get("template_instructions", "")
        return "纪要"

    monkeypatch.setattr(minutes_service, "generate_text", fake_generate)
    headers = _auth(client)
    from sqlalchemy import select

    from app.models.user import User
    from app.repositories import meeting_template_repository

    user_id = db_session.execute(select(User)).scalars().one().user_id
    meeting_template_repository.create(
        db_session,
        template_id="tpl_custom_default",
        user_id=user_id,
        name="自定义默认模板",
        description=None,
        content_text="自定义结构要求",
    )
    client.put(
        PATH,
        json={"preferred_minutes_template": "tpl_custom_default"},
        headers=headers,
    )
    meeting = client.post(
        "/api/v1/meetings", json={"title": "周会"}, headers=headers
    ).json()["data"]

    generated = client.post(
        f"/api/v1/meetings/{meeting['meeting_id']}/minutes/generate",
        json={"record_ids": []},
        headers=headers,
    )

    assert generated.status_code == 201
    assert generated.json()["data"]["template"] == "custom"
    assert captured["template_instructions"] == "自定义结构要求"


def test_preferred_builtin_list_id_accepted(client: TestClient) -> None:
    """默认模板指向内置清单 id（如 tpl-builtin-minutes）同样合法。"""
    headers = _auth(client)
    saved = client.put(
        PATH,
        json={"preferred_minutes_template": "tpl-builtin-minutes"},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["preferred_minutes_template"] == "tpl-builtin-minutes"
