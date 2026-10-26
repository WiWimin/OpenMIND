import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import knowledge_service

BASE = "/api/v1/knowledge"
REGISTER = "/api/v1/auth/register"
PASSWORD = "secret123"

_VECTOR = [1.0] + [0.0] * 1023


@pytest.fixture()
def media_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    base = get_settings()

    def fake_settings():
        return base.model_copy(update={"storage_dir": str(tmp_path)})

    monkeypatch.setattr(knowledge_service, "get_settings", fake_settings)
    return tmp_path


@pytest.fixture()
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_service,
        "embed_texts",
        lambda texts, client: [list(_VECTOR) for _ in texts],
    )
    monkeypatch.setattr(
        knowledge_service,
        "embed_query",
        lambda text, config: list(_VECTOR),
    )


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": name, "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    file_name: str = "notes.txt",
    content: bytes = b"Alpha beta",
):
    return client.post(
        f"{BASE}/documents",
        files={"file": (file_name, content, "text/plain")},
        headers=headers,
    )


def _search(client: TestClient, headers: dict[str, str], query: str):
    return client.post(
        f"{BASE}/search",
        json={"query": query},
        headers=headers,
    )


def test_upload_lists_and_reads_document(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)

    uploaded = _upload(client, headers)

    assert uploaded.status_code == 201, uploaded.text
    data = uploaded.json()["data"]
    assert data["document_id"].startswith("kdoc_")
    assert data["file_name"] == "notes.txt"
    assert data["type"] == "txt"
    assert data["processing_status"] == "processed"

    listing = client.get(f"{BASE}/documents", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total"] == 1

    found = client.get(f"{BASE}/documents/{data['document_id']}", headers=headers)
    assert found.status_code == 200
    assert found.json()["data"]["document_id"] == data["document_id"]


def test_search_returns_owned_hits(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)
    document = _upload(client, headers).json()["data"]

    response = _search(client, headers, "alpha")

    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["document_id"] == document["document_id"]
    assert "Alpha" in items[0]["excerpt"]
    assert items[0]["score"] == pytest.approx(1.0)


def test_search_is_isolated_between_users(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    alice = _auth(client, "alice")
    _upload(client, alice)
    bob = _auth(client, "bob")

    response = _search(client, bob, "alpha")

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


def test_cross_user_access_returns_404(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    alice = _auth(client, "alice")
    document = _upload(client, alice).json()["data"]
    bob = _auth(client, "bob")

    assert client.get(f"{BASE}/documents/{document['document_id']}", headers=bob).status_code == 404
    assert (
        client.delete(f"{BASE}/documents/{document['document_id']}", headers=bob).status_code
        == 404
    )


def test_delete_removes_document_and_chunks(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)
    document = _upload(client, headers).json()["data"]

    deleted = client.delete(f"{BASE}/documents/{document['document_id']}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["data"] == {
        "deleted": True,
        "document_id": document["document_id"],
    }
    assert (
        client.get(
            f"{BASE}/documents/{document['document_id']}", headers=headers
        ).status_code
        == 404
    )
    assert _search(client, headers, "alpha").json()["data"]["items"] == []


def test_unsupported_file_type_rejected(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)

    response = _upload(client, headers, file_name="bad.exe", content=b"x")

    assert response.status_code == 415
    assert response.json()["error_code"] == "FILE_TYPE_NOT_SUPPORTED"


def test_parse_failure_is_reported(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)

    response = _upload(client, headers, file_name="bad.pdf", content=b"not a pdf")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["processing_status"] == "failed"
    assert data["parse_error"]


def test_empty_search_query_rejected(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)

    response = _search(client, headers, "")

    assert response.status_code == 422


def test_list_pagination(
    client: TestClient, media_root, fake_embeddings: None
) -> None:
    headers = _auth(client)
    _upload(client, headers, file_name="one.txt", content=b"one")
    _upload(client, headers, file_name="two.txt", content=b"two")

    response = client.get(
        f"{BASE}/documents", params={"page": 1, "page_size": 1}, headers=headers
    )

    data = response.json()["data"]
    assert data["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert len(data["items"]) == 1


def test_requires_auth(client: TestClient) -> None:
    assert client.get(f"{BASE}/documents").status_code == 401
    assert client.post(f"{BASE}/search", json={"query": "x"}).status_code == 401
