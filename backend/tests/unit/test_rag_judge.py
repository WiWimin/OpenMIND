"""RAG 相关性 Judge：低分带复核、回退与高分直通。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.orm import Session

from app.ai.llm import LLMClient
from app.ai.rag import retriever as rag
from app.ai.rag.relevance import RelevanceJudge
from app.models.chunk import DocumentChunk
from app.repositories import (
    material_repository,
    meeting_repository,
    user_repository,
)

# 查询向量 [1,0] 与分块向量 [0.5, 0.866] 的余弦 = 0.5，落在
# min_score(0.3) 与 judge_min_score(0.6) 之间的“低分带”。
_LOW_SCORE_EMBEDDING = [0.5, 0.8660254]


def _seed_low_score_chunk(db: Session, name: str) -> str:
    user = user_repository.create(
        db, user_id=f"usr_{name}", name=name, password_hash="x"
    )
    meeting_repository.create(
        db,
        meeting_id=f"mtg_{name}",
        user_id=user.user_id,
        title="周会",
        topic=None,
        meeting_time=None,
    )
    material_repository.create(
        db,
        material_id=f"mat_{name}",
        meeting_id=f"mtg_{name}",
        user_id=user.user_id,
        file_name="a.txt",
        material_type="txt",
        source=None,
        storage_key=f"materials/mat_{name}.txt",
    )
    db.add(
        DocumentChunk(
            chunk_id=f"chk_{name}",
            material_id=f"mat_{name}",
            content="食堂菜单内容与本问题无关",
            chunk_index=0,
            embedding=_LOW_SCORE_EMBEDDING,
        )
    )
    db.commit()
    return user.user_id


class _FakeJudge:
    def __init__(self, verdict: bool | None) -> None:
        self.verdict = verdict
        self.calls: list[str] = []

    def is_relevant(self, query: str, excerpts: list[str]) -> bool | None:
        self.calls.append(query)
        assert excerpts, "Judge 应收到至少一个候选"
        return self.verdict


def _patch_judge_env(
    monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True, min_score: float = 0.6
) -> None:
    monkeypatch.setattr(
        rag,
        "get_settings",
        lambda: SimpleNamespace(
            rag_judge_enabled=enabled, rag_judge_min_score=min_score
        ),
    )
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])


def _patch_judge(monkeypatch: pytest.MonkeyPatch, verdict: bool | None) -> _FakeJudge:
    fake = _FakeJudge(verdict)
    monkeypatch.setattr(
        rag.VectorRetriever,
        "_build_judge",
        staticmethod(lambda config: fake),
    )
    return fake


def _retrieve(db: Session, user_id: str) -> list:
    return rag.VectorRetriever(db, user_id).retrieve(
        "公司食堂下周菜单是什么", user_id=user_id, scope="current_meeting"
    )


def test_judge_rejects_low_score_negative(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_low_score_chunk(db_session, "judge-a")
    _patch_judge_env(monkeypatch)
    fake = _patch_judge(monkeypatch, verdict=False)

    results = _retrieve(db_session, user_id)

    assert results == []
    assert fake.calls == ["公司食堂下周菜单是什么"]


def test_judge_keeps_results_when_relevant(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_low_score_chunk(db_session, "judge-b")
    _patch_judge_env(monkeypatch)
    _patch_judge(monkeypatch, verdict=True)

    assert len(_retrieve(db_session, user_id)) == 1


def test_judge_unavailable_falls_back_to_score(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_low_score_chunk(db_session, "judge-c")
    _patch_judge_env(monkeypatch)
    _patch_judge(monkeypatch, verdict=None)

    assert len(_retrieve(db_session, user_id)) == 1


def test_high_score_bypasses_judge(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_low_score_chunk(db_session, "judge-d")
    _patch_judge_env(monkeypatch)
    # 高分带（score=1.0 ≥ 0.6）不得触达 Judge
    monkeypatch.setattr(
        rag.VectorRetriever,
        "_build_judge",
        staticmethod(
            lambda config: pytest.fail("高分带不应构造 Judge")
        ),
    )
    monkeypatch.setattr(rag, "embed_query", lambda text, config: [1.0, 0.0])
    # 分块向量与查询一致 → score 1.0
    chunk = db_session.get(DocumentChunk, "chk_judge-d")
    chunk.embedding = [1.0, 0.0]
    db_session.commit()

    assert len(_retrieve(db_session, user_id)) == 1


def test_judge_disabled_keeps_score_only(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _seed_low_score_chunk(db_session, "judge-e")
    _patch_judge_env(monkeypatch, enabled=False)
    monkeypatch.setattr(
        rag.VectorRetriever,
        "_build_judge",
        staticmethod(lambda config: pytest.fail("Judge 已禁用不应构造")),
    )

    assert len(_retrieve(db_session, user_id)) == 1


def test_relevance_judge_parses_structured_verdict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"relevant": false}'}}
                ],
                "model": "m",
                "usage": {},
            },
        )

    client = LLMClient(
        api_base="https://llm.example.com/v1",
        api_key="k",
        model="m",
        transport=httpx.MockTransport(handler),
    )
    judge = RelevanceJudge(config=None, client=client)  # type: ignore[arg-type]

    assert judge.is_relevant("问题", ["候选内容"]) is False


def test_relevance_judge_unavailable_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    client = LLMClient(
        api_base="https://llm.example.com/v1",
        api_key="k",
        model="m",
        transport=httpx.MockTransport(handler),
    )
    judge = RelevanceJudge(config=None, client=client)  # type: ignore[arg-type]

    assert judge.is_relevant("问题", ["候选内容"]) is None
