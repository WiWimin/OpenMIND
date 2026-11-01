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


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        url_validation,
        "_resolve_host",
        lambda host, port: {"93.184.216.34"},
    )


@pytest.fixture()
def fake_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_config_service.LLMClient, "probe", lambda self, **k: None)


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
    }


def test_put_and_get_masks_keys(client: TestClient, fake_probe: None) -> None:
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    assert response.status_code == 200, response.text
    assert LLM_KEY not in response.text
    data = response.json()["data"]
    assert data["llm_api_key_masked"].startswith("sk-")
    assert data["llm_api_key_masked"].endswith("-key")
    assert data["llm_model"] == "custom-model"
    assert data["llm_source"] == "user"
    assert data["llm_probe_verified"] is True
    # 向量模型不支持用户自备，来源只能是服务端配置或未配置
    assert data["embedding_source"] in ("global", "none")

    got = client.get("/api/v1/me/settings/model", headers=headers)
    assert got.status_code == 200
    assert LLM_KEY not in got.text


def test_keys_encrypted_at_rest(
    client: TestClient, db_session: Session, fake_probe: None
) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)
    row = db_session.execute(select(UserModelConfig)).scalars().one()
    assert row.llm_api_key_enc != LLM_KEY
    assert LLM_KEY not in row.llm_api_key_enc


def test_config_isolated_per_user(client: TestClient, fake_probe: None) -> None:
    alice = _auth(client, "alice")
    bob = _auth(client, "bob")
    client.put("/api/v1/me/settings/model", json=_payload(), headers=alice)

    bob_read = client.get("/api/v1/me/settings/model", headers=bob).json()["data"]
    assert bob_read["llm_model"] == ""
    assert bob_read["llm_model"] != "custom-model"
    assert bob_read["llm_source"] == "none"
    assert bob_read["llm_api_key_masked"] == ""


def test_global_keys_are_not_masked_or_returned(
    client: TestClient, fake_probe: None, monkeypatch: pytest.MonkeyPatch
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
    client: TestClient, fake_probe: None
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
    client: TestClient, fake_probe: None
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
    client: TestClient, fake_probe: None
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
    client: TestClient, fake_probe: None
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
    client: TestClient, fake_probe: None
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


def test_private_api_base_rejected(client: TestClient, fake_probe: None) -> None:
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


def test_llm_probe_rate_limited_still_saves(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """probe 遇 429 限流视为密钥有效，放行保存并返回未验证标志。"""

    def rate_limited(self, **kwargs):
        raise AppError("RATE_LIMITED", "模型服务限流", http_status=429, retryable=True)

    monkeypatch.setattr(model_config_service.LLMClient, "probe", rate_limited)
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["llm_source"] == "user"
    assert data["llm_probe_verified"] is False


def test_llm_probe_failure_blocks_save(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(self, **kwargs):
        raise AppError("MODEL_TIMEOUT", "模型调用超时", http_status=504, retryable=True)

    monkeypatch.setattr(model_config_service.LLMClient, "probe", timeout)
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    assert response.status_code == 504
    body = response.json()
    assert body["error_code"] == "MODEL_TIMEOUT"
    assert body["retryable"] is True


def test_llm_probe_invalid_key_blocks_save(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid_key(self, **kwargs):
        raise AppError("MODEL_CONFIG_INVALID", "模型密钥无效或已失效", http_status=400)

    monkeypatch.setattr(model_config_service.LLMClient, "probe", invalid_key)
    headers = _auth(client)
    response = client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"


def test_partial_provider_requires_all_fields(client: TestClient, fake_probe: None) -> None:
    headers = _auth(client)
    response = client.put(
        "/api/v1/me/settings/model",
        json={"llm_api_base": "https://llm.example.com/v1"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_INVALID"


def test_delete_clears_config(client: TestClient, fake_probe: None) -> None:
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    deleted = client.delete("/api/v1/me/settings/model", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    after = client.get("/api/v1/me/settings/model", headers=headers).json()["data"]
    assert after["llm_model"] == ""
    assert after["llm_model"] != "custom-model"
    assert after["llm_source"] == "none"


def test_provider_models_requires_configured_llm(client: TestClient) -> None:
    headers = _auth(client)
    response = client.get("/api/v1/me/settings/model/provider-models", headers=headers)
    assert response.status_code == 400
    assert response.json()["error_code"] == "MODEL_CONFIG_REQUIRED"


def test_provider_models_returns_list(
    client: TestClient, fake_probe: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_config_service.LLMClient,
        "list_models",
        lambda self, **k: ["model-a", "model-b"],
    )
    headers = _auth(client)
    client.put("/api/v1/me/settings/model", json=_payload(), headers=headers)

    response = client.get("/api/v1/me/settings/model/provider-models", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["llm_model"] == "custom-model"
    assert data["models"] == ["model-a", "model-b"]


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/me/settings/model").status_code == 401
    assert client.put("/api/v1/me/settings/model", json={}).status_code == 401
    assert client.delete("/api/v1/me/settings/model").status_code == 401
