import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import url_validation
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.model_config import UserModelConfig
from app.models.user import User
from app.services import model_config_service

REGISTER = "/api/v1/auth/register"
PASSWORD = "secret123"

LLM_KEY = "sk-llm-secret-key"
EMB_KEY = "sk-emb-secret-key"


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        url_validation,
        "_resolve_host",
        lambda host, port: {"93.184.216.34"},
    )


@pytest.fixture()
def fake_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_config_service, "_probe_embedding_dim", lambda *a, **k: None)
    monkeypatch.setattr(model_config_service, "_probe_llm", lambda *a, **k: None)


def _auth(client: TestClient, name: str = "alice") -> dict[str, str]:
    token = client.post(
        REGISTER, json={"name": name, "password": PASSWORD}
    ).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _payload() -> dict:
    return {
        "llm_api_base": "https://llm.example.com/v1",
        "llm_api_key": LLM_KEY,
        "llm_model": "custom-model",
        "embedding_api_base": "https://emb.example.com/v1",
        "embedding_api_key": EMB_KEY,
        "embedding_model": "text-embedding-1024",
    }


def test_put_and_get_masks_keys(client: TestClient, fake_probes: None) -> None:
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    assert response.status_code == 200, response.text
    assert LLM_KEY not in response.text
    data = response.json()["data"]
    assert data["llm_api_key_masked"].startswith("sk-")
    assert data["llm_api_key_masked"].endswith("-key")
    assert data["llm_model"] == "custom-model"
    assert data["llm_source"] == "user"
    assert data["embedding_source"] == "user"
    assert data["embedding_dim"] == 1024

    got = client.get("/api/v1/me/settings/model", headers=headers)
    assert got.status_code == 200
    assert LLM_KEY not in got.text
    assert EMB_KEY not in got.text


def test_keys_encrypted_at_rest(
    client: TestClient, db_session: Session, fake_probes: None
) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    row = db_session.execute(select(UserModelConfig)).scalars().one()
    assert row.llm_api_key_enc != LLM_KEY
    assert LLM_KEY not in row.llm_api_key_enc
    assert EMB_KEY not in row.embedding_api_key_enc


def test_config_isolated_per_user(client: TestClient, fake_probes: None) -> None:
    alice = _auth(client, "alice")
    bob = _auth(client, "bob")
    client.put("/api/v1/me/settings/model", json=_payload(), headers=alice)

    bob_read = client.get("/api/v1/me/settings/model", headers=bob).json()["data"]
    assert bob_read["llm_model"] == ""
    assert bob_read["llm_model"] != "custom-model"
    assert bob_read["llm_source"] == "none"
    assert bob_read["llm_api_key_masked"] == ""


def test_global_keys_are_not_masked_or_returned(
    client: TestClient, fake_probes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = get_settings()
    monkeypatch.setattr(
        model_config_service,
        "get_settings",
        lambda: base.model_copy(
            update={
                "llm_api_base": "https://example.com/v1",
                "llm_api_key": "sk-global-secret",
                "llm_model": "global-model",
                "embedding_api_base": "https://example.com/v1",
                "embedding_api_key": "sk-global-embedding",
                "embedding_model": "global-embedding",
                "allow_global_fallback": True,
            }
        ),
    )
    alice = _auth(client, "alice")
    bob = _auth(client, "bob")
    client.put("/api/v1/me/settings/model", json=_payload(), headers=alice)

    bob_read = client.get("/api/v1/me/settings/model", headers=bob).json()["data"]
    assert bob_read["llm_source"] == "global"
    assert bob_read["llm_api_key_masked"] == ""
    assert bob_read["embedding_source"] == "global"
    assert bob_read["embedding_api_key_masked"] == ""


def test_put_purpose_models_and_read(
    client: TestClient, fake_probes: None
) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    response = client.put(
        "/api/v1/me/settings/model/purposes",
        json={"models": {"minutes": "minutes-model", "chat": "chat-model"}},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["llm_purpose_models"] == {
        "minutes": "minutes-model",
        "chat": "chat-model",
    }
    got = client.get("/api/v1/me/settings/model", headers=headers).json()["data"]
    assert got["llm_purpose_models"]["minutes"] == "minutes-model"


def test_purpose_models_require_configured_llm(
    client: TestClient, fake_probes: None
) -> None:
    headers = _auth(client)

    response = client.put(
        "/api/v1/me/settings/model/purposes",
        json={"models": {"minutes": "minutes-model"}},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"


def test_unknown_purpose_model_rejected(
    client: TestClient, fake_probes: None
) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    response = client.put(
        "/api/v1/me/settings/model/purposes",
        json={"models": {"unknown": "some-model"}},
        headers=headers,
    )

    assert response.status_code == 422


def test_empty_purpose_models_clear_overrides(
    client: TestClient, fake_probes: None
) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    client.put(
        "/api/v1/me/settings/model/purposes",
        json={"models": {"minutes": "minutes-model"}},
        headers=headers,
    )

    response = client.put(
        "/api/v1/me/settings/model/purposes",
        json={"models": {}},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["llm_purpose_models"] == {}


def test_base_config_save_preserves_purpose_models(
    client: TestClient, fake_probes: None
) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    client.put(
        "/api/v1/me/settings/model/purposes",
        json={"models": {"minutes": "minutes-model"}},
        headers=headers,
    )

    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    got = client.get("/api/v1/me/settings/model", headers=headers).json()["data"]
    assert got["llm_purpose_models"] == {"minutes": "minutes-model"}


def test_private_api_base_rejected(client: TestClient, fake_probes: None) -> None:
    headers = _auth(client)
    payload = _payload()
    payload["llm_api_base"] = "https://127.0.0.1:8000/v1"

    response = client.put("/api/v1/me/settings/model", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"


def test_undecryptable_key_returns_model_config_invalid(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth(client)
    user = db_session.execute(select(User)).scalars().one()
    db_session.add(
        UserModelConfig(
            user_id=user.user_id,
            llm_api_base="https://example.com/v1",
            llm_api_key_enc="not-a-valid-fernet-token",
            llm_model="custom-model",
        )
    )
    db_session.commit()

    response = client.get("/api/v1/me/settings/model", headers=headers)
    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"

    deleted = client.delete("/api/v1/me/settings/model", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/v1/me/settings/model", headers=headers).status_code == 200


def test_embedding_dim_mismatch_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def bad_dim(*args, **kwargs):
        raise AppError(
            "MODEL_CONFIG_INVALID", "Embedding 校验失败：向量维度必须为 1024", http_status=400
        )

    monkeypatch.setattr(model_config_service, "_probe_embedding_dim", bad_dim)
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"


def test_embedding_probe_network_error_returns_retryable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def network_error(*args, **kwargs):
        raise AppError(
            "INTERNAL_ERROR",
            "Embedding 校验失败：向量服务网络异常",
            http_status=500,
            retryable=True,
        )

    monkeypatch.setattr(model_config_service, "_probe_embedding_dim", network_error)
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["retryable"] is True


def test_partial_provider_requires_all_fields(client: TestClient, fake_probes: None) -> None:
    headers = _auth(client)
    response = client.put(
        "/api/v1/me/settings/model",
        json={"llm_api_base": "https://llm.example.com/v1"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"


def test_delete_clears_config(client: TestClient, fake_probes: None) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    deleted = client.delete("/api/v1/me/settings/model", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    after = client.get("/api/v1/me/settings/model", headers=headers).json()["data"]
    assert after["llm_model"] == ""
    assert after["llm_model"] != "custom-model"
    assert after["llm_source"] == "none"
    assert after["embedding_source"] == "none"


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/me/settings/model").status_code == 401
    assert client.put("/api/v1/me/settings/model", json={}).status_code == 401
    assert client.delete("/api/v1/me/settings/model").status_code == 401
