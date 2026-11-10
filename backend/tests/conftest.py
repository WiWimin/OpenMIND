import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret-key-" + "a" * 32)
# 单测/接口测试禁用 RAG 相关性 Judge：避免低分带查询触发真实 LLM 调用
# （Judge 行为由 tests/unit/test_rag_judge.py 显式开关覆盖）
os.environ.setdefault("RAG_JUDGE_ENABLED", "false")
# 单测/接口测试禁用联网检索：拒答路径由测试显式开关覆盖，不发起真实搜索
os.environ.setdefault("WEB_SEARCH_ENABLED", "false")
# 限流在默认用例中关闭（注册/登录密集会被误伤），限流行为由
# tests/unit/test_rate_limit.py 显式开关覆盖
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# 异步长任务默认关闭：绝大多数用例断言同步语义（201/200）；
# 异步行为由 tests/api/test_jobs.py 显式开启（monkeypatch + 缓存清理）
os.environ.setdefault("ASYNC_JOBS_ENABLED", "false")

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


@pytest.fixture(autouse=True)
def _clean_metrics() -> Iterator[None]:
    """检索/Judge 埋点写入进程内指标，用例间必须清零避免串扰。"""
    from app.core import metrics

    metrics.reset()
    try:
        yield
    finally:
        metrics.reset()


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
    # 后台任务（含启动回收）用独立会话：替换为测试内存库的 sessionmaker，
    # 必须在进入 TestClient（触发 lifespan）之前设置
    from app.services import task_runner

    original_factory = task_runner.session_factory
    task_runner.session_factory = testing_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        task_runner.session_factory = original_factory
        app.dependency_overrides.clear()
