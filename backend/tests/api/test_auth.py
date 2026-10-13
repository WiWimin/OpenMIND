from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"

PASSWORD = "secret123"


def _register(client: TestClient, name: str = "alice") -> dict:
    return client.post(REGISTER, json={"name": name, "password": PASSWORD}).json()


def test_register_returns_session(client: TestClient) -> None:
    response = client.post(REGISTER, json={"name": "alice", "password": PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["name"] == "alice"
    assert data["user"]["user_id"].startswith("usr_")
    assert "password_hash" not in response.text


def test_register_duplicate_name_conflict(client: TestClient) -> None:
    _register(client)
    response = client.post(REGISTER, json={"name": "alice", "password": PASSWORD})
    assert response.status_code == 409
    assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"


def test_register_password_too_short(client: TestClient) -> None:
    response = client.post(REGISTER, json={"name": "bob", "password": "123"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_login_success(client: TestClient) -> None:
    _register(client)
    response = client.post(LOGIN, json={"name": "alice", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["data"]["user"]["name"] == "alice"


def test_login_wrong_password(client: TestClient) -> None:
    _register(client)
    response = client.post(LOGIN, json={"name": "alice", "password": "wrong-pass"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_login_unknown_user(client: TestClient) -> None:
    response = client.post(LOGIN, json={"name": "ghost", "password": PASSWORD})
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_me_requires_token(client: TestClient) -> None:
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_me_returns_current_user(client: TestClient) -> None:
    token = _register(client)["data"]["access_token"]
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "alice"


def test_me_invalid_token(client: TestClient) -> None:
    response = client.get(ME, headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_logout(client: TestClient) -> None:
    response = client.post(LOGOUT)
    assert response.status_code == 200
    assert response.json()["data"] == {"logged_out": True}
