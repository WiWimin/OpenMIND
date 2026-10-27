import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import material_service

REGISTER = "/api/v1/auth/register"
MEETINGS = "/api/v1/meetings"

PASSWORD = "secret123"


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(material_service, "get_settings", fake_settings)
    return tmp_path


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    response = client.post(REGISTER, json={"name": name, "password": PASSWORD})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_meeting(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(MEETINGS, json={"title": "资料会议"}, headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _upload(
    client: TestClient,
    headers: dict[str, str],
    meeting_id: str,
    *,
    name: str = "项目方案.txt",
    content: bytes = b"hello",
    data: dict | None = None,
):
    files = {"file": (name, content, "application/octet-stream")}
    return client.post(
        f"/api/v1/meetings/{meeting_id}/materials",
        files=files,
        data=data or {},
        headers=headers,
    )


def test_upload_material(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)

    response = _upload(client, headers, meeting["meeting_id"], data={"source": "会前材料"})
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["material_id"].startswith("mat_")
    assert data["meeting_id"] == meeting["meeting_id"]
    assert data["file_name"] == "项目方案.txt"
    assert data["type"] == "txt"
    assert data["source"] == "会前材料"
    assert data["processing_status"] == "processed"
    assert data["parse_error"] is None
    assert "storage_key" not in data
    assert (media_root / "materials" / f"{data['material_id']}.txt").exists()


def test_upload_parse_failure_returns_failed_material(
    client: TestClient, media_root
) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)

    response = _upload(
        client,
        headers,
        meeting["meeting_id"],
        name="broken.pdf",
        content=b"not a real pdf",
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["processing_status"] == "failed"
    assert data["parse_error"]


def test_upload_requires_auth(client: TestClient, media_root) -> None:
    response = client.post(
        "/api/v1/meetings/mtg_x/materials",
        files={"file": ("a.txt", b"hi", "text/plain")},
    )
    assert response.status_code == 401


def test_upload_unsupported_type(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    response = _upload(client, headers, meeting["meeting_id"], name="virus.exe")
    assert response.status_code == 415
    assert response.json()["error_code"] == "FILE_TYPE_NOT_SUPPORTED"


def test_upload_too_large(client: TestClient, media_root, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    base = get_settings()

    def tiny_settings():
        return base.model_copy(update={"storage_dir": str(media_root), "max_upload_mb": 0})

    monkeypatch.setattr(material_service, "get_settings", tiny_settings)

    response = _upload(client, headers, meeting["meeting_id"], content=b"some-bytes")
    assert response.status_code == 413
    assert response.json()["error_code"] == "FILE_TOO_LARGE"


def test_upload_meeting_not_found(client: TestClient, media_root) -> None:
    headers = _auth(client)
    response = _upload(client, headers, "mtg_missing")
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_upload_cross_user_forbidden(client: TestClient, media_root) -> None:
    alice = _auth(client, "alice")
    meeting = _create_meeting(client, alice)
    bob = _auth(client, "bob")
    response = _upload(client, bob, meeting["meeting_id"])
    assert response.status_code == 404


def test_list_materials(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    _upload(client, headers, meeting["meeting_id"], name="a.txt")
    _upload(client, headers, meeting["meeting_id"], name="b.txt")

    response = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/materials", headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pagination"] == {"page": 1, "page_size": 20, "total": 2, "total_pages": 1}
    assert len(data["items"]) == 2


def test_get_material_and_cross_user(client: TestClient, media_root) -> None:
    alice = _auth(client, "alice")
    meeting = _create_meeting(client, alice)
    material = _upload(client, alice, meeting["meeting_id"]).json()["data"]

    found = client.get(f"/api/v1/materials/{material['material_id']}", headers=alice)
    assert found.status_code == 200
    assert found.json()["data"]["material_id"] == material["material_id"]

    bob = _auth(client, "bob")
    url = f"/api/v1/materials/{material['material_id']}"
    assert client.get(url, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404


def test_delete_material_clears_record_source(
    client: TestClient, media_root, db_session
) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    material = _upload(client, headers, meeting["meeting_id"]).json()["data"]

    from app.repositories import record_repository

    record_repository.create(
        db_session,
        record_id="rec_source",
        meeting_id=meeting["meeting_id"],
        content="来源记录",
        record_type="imported",
        source_material_id=material["material_id"],
    )

    response = client.delete(
        f"/api/v1/materials/{material['material_id']}", headers=headers
    )
    assert response.status_code == 200

    records = client.get(
        f"/api/v1/meetings/{meeting['meeting_id']}/records", headers=headers
    ).json()["data"]["items"]
    source_record = next(item for item in records if item["record_id"] == "rec_source")
    assert source_record["source_material_id"] is None


def test_delete_material_removes_row_and_file(client: TestClient, media_root) -> None:
    headers = _auth(client)
    meeting = _create_meeting(client, headers)
    material = _upload(client, headers, meeting["meeting_id"]).json()["data"]
    path = media_root / "materials" / f"{material['material_id']}.txt"
    assert path.exists()

    response = client.delete(f"/api/v1/materials/{material['material_id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "deleted": True,
        "material_id": material["material_id"],
    }
    assert not path.exists()
    assert (
        client.get(f"/api/v1/materials/{material['material_id']}", headers=headers).status_code
        == 404
    )
