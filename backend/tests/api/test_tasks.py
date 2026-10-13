from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories import task_repository

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


def test_update_task_status_transitions(client: TestClient, db_session: Session) -> None:
    headers, user_id = _register(client)
    _seed(db_session, user_id, task_id="tsk_1", status="todo")

    started = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "in_progress"}, headers=headers
    )
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "in_progress"

    client.patch("/api/v1/tasks/tsk_1", json={"status": "completed"}, headers=headers)
    reopened = client.patch(
        "/api/v1/tasks/tsk_1", json={"status": "in_progress"}, headers=headers
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
