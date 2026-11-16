from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories import meeting_repository, task_repository

REGISTER = "/api/v1/auth/register"

PASSWORD = "secret123"


def _register(client: TestClient, name: str = "alice") -> tuple[dict[str, str], str]:
    data = client.post(REGISTER, json={"name": name, "password": PASSWORD}).json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]["user_id"]


def _seed(
    db: Session,
    user_id: str,
    *,
    task_id: str,
    title: str = "任务",
    status: str = "todo",
    due_date: date | None = None,
) -> None:
    task_repository.create(
        db,
        task_id=task_id,
        user_id=user_id,
        meeting_id=None,
        action_id=None,
        title=title,
        due_date=due_date,
        status=status,
    )


def test_list_tasks_and_filter(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", title="A")
    _seed(db_session, user_id, task_id="tsk_2", title="B", status="completed")

    listing = client.get("/api/v1/tasks", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total"] == 2

    completed = client.get("/api/v1/tasks", params={"status": "completed"}, headers=headers)
    assert completed.json()["data"]["pagination"]["total"] == 1
    assert completed.json()["data"]["items"][0]["task_id"] == "tsk_2"


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/tasks").status_code == 401


def test_get_and_cross_user(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client, "alice")
    _seed(db_session, user_id, task_id="tsk_x")

    assert client.get("/api/v1/tasks/tsk_x", headers=headers).status_code == 200

    bob_headers, _ = _register(client, "bob")
    assert client.get("/api/v1/tasks/tsk_x", headers=bob_headers).status_code == 404
    assert client.post("/api/v1/tasks/tsk_x/cancel", headers=bob_headers).status_code == 404


def test_update_task_fields(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", title="旧标题")

    response = client.patch(
        "/api/v1/tasks/tsk_1",
        json={"title": "新标题", "due_date": "2026-10-09"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "新标题"
    assert data["due_date"] == "2026-10-09"


def test_create_task(client: TestClient) -> None:
    headers, _ = _register(client)

    response = client.post(
        "/api/v1/tasks",
        json={"title": "买牛奶", "due_date": "2026-11-20"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "买牛奶"
    assert data["status"] == "todo"
    assert data["due_date"] == "2026-11-20"
    assert data["meeting_id"] is None


def test_create_task_requires_title(client: TestClient) -> None:
    headers, _ = _register(client)

    response = client.post("/api/v1/tasks", json={"title": ""}, headers=headers)
    assert response.status_code == 422


def test_create_task_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/tasks", json={"title": "无鉴权"})
    assert response.status_code == 401


def test_todo_can_complete_directly(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="todo")

    response = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"


def test_completed_can_revert_to_todo(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="completed")

    response = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "todo"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "todo"


def test_cancelled_is_terminal(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="cancelled")

    response = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "todo"}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"


def test_update_task_status_transitions(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="todo")

    started = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "in_progress"}, headers=headers
    )
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "in_progress"

    completed = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "completed"}, headers=headers
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "completed"

    # 终态（completed → cancelled）不允许
    reopened = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "cancelled"}, headers=headers
    )
    assert reopened.status_code == 409
    assert reopened.json()["error_code"] == "BUSINESS_RULE_VIOLATION"


def test_cancel_task_idempotent(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="todo")

    first = client.post("/api/v1/tasks/tsk_1/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "cancelled"

    second = client.post("/api/v1/tasks/tsk_1/cancel", headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "cancelled"


def test_cancel_completed_task_conflict(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="completed")

    response = client.post("/api/v1/tasks/tsk_1/cancel", headers=headers)
    assert response.status_code == 409


def test_create_task_priority_default_and_override(client: TestClient) -> None:
    headers, _ = _register(client)

    default = client.post("/api/v1/tasks", json={"title": "默认优先级"}, headers=headers)
    assert default.status_code == 201
    assert default.json()["data"]["priority"] == "medium"

    high = client.post(
        "/api/v1/tasks", json={"title": "高优先级", "priority": "high"}, headers=headers
    )
    assert high.status_code == 201
    assert high.json()["data"]["priority"] == "high"


def test_create_task_invalid_priority_rejected(client: TestClient) -> None:
    headers, _ = _register(client)

    response = client.post(
        "/api/v1/tasks", json={"title": "错误优先级", "priority": "urgent"}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_update_task_priority(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1")

    response = client.patch("/api/v1/tasks/tsk_1", json={"priority": "low"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["priority"] == "low"


def test_list_tasks_includes_meeting_title(
    client: TestClient, db_session: Session
) -> None:
    headers, user_id = _register(client)
    meeting = meeting_repository.create(
        db_session,
        meeting_id="mtg_task_title",
        user_id=user_id,
        title="需求评审会",
        topic=None,
        meeting_time=None,
    )
    task_repository.create(
        db_session,
        task_id="tsk_with_meeting",
        user_id=user_id,
        meeting_id=meeting.meeting_id,
        action_id=None,
        title="整理评审结论",
        due_date=None,
    )
    task_repository.create(
        db_session,
        task_id="tsk_without_meeting",
        user_id=user_id,
        meeting_id=None,
        action_id=None,
        title="独立任务",
        due_date=None,
    )

    items = {
        item["task_id"]: item
        for item in client.get("/api/v1/tasks", headers=headers).json()["data"]["items"]
    }
    assert items["tsk_with_meeting"]["meeting_title"] == "需求评审会"
    assert items["tsk_without_meeting"]["meeting_title"] is None
