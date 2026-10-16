from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  在 Base.metadata 上注册 ORM 模型
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _fake_indexing_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import indexing_service

    monkeypatch.setattr(
        indexing_service,
        "embed_texts",
        lambda texts, client: [[0.0] * 1024 for _ in texts],
    )


@pytest.fixture()
def db_engine() -> Iterator[Engine]:
    """每个用例一个独立的 SQLite 内存库，CI 无需 PostgreSQL。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Iterator[Session]:
    """与 `client` 共享同一内存库的直连会话，用于测试内直接造数。"""
    testing_session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine: Engine) -> Iterator[TestClient]:
    testing_session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
