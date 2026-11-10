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


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """模型重试的退避与 deadline 用假时钟：不真实 sleep，且可被用例拨动。

    只替换 `app.ai.http_client` 模块内的 `time` 属性（非全局 `time` 模块），
    其他模块的真实 `time.sleep`（如限流用例）不受影响。
    用例可通过 `app.ai.http_client.time.sleeps / .now` 断言等待与推进时间。
    """
    import app.ai.http_client as http_client

    class _FakeTime:
        def __init__(self) -> None:
            self.now = 1_000.0
            self.sleeps: list[float] = []

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.sleeps.append(seconds)
            self.now += seconds

    monkeypatch.setattr(http_client, "time", _FakeTime())
    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(autouse=True)
def _clean_connection_pool() -> Iterator[None]:
    """每个用例后关闭池化 HTTP 客户端，避免跨用例复用连接。"""
    from app.ai import connection

    connection.close_ai_clients()
    try:
        yield
    finally:
        connection.close_ai_clients()


@pytest.fixture(autouse=True)
def _clean_resilience() -> Iterator[None]:
    """并发闸门与熔断状态按用例清零，避免跨用例串扰。"""
    from app.ai import resilience

    resilience.reset()
    try:
        yield
    finally:
        resilience.reset()


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
