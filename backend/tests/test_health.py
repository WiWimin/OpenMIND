import pytest
from fastapi.testclient import TestClient

from app.api.v1 import health as health_module


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "OpenMIND"


def test_db_health_up(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "check_database", lambda: True)
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_db_health_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "check_database", lambda: False)
    response = client.get("/api/v1/health/db")
    assert response.status_code == 503


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error_code"] == "RESOURCE_NOT_FOUND"
    assert "message" in body
