from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import material_repository


@dataclass(frozen=True)
class RetrievedChunk:
    meeting_id: str
    material_id: str
    record_id: str | None
    excerpt: str
    score: float


def _split_chunks(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _score(query: str, chunk: str) -> float:
    query_chars = {char for char in query if not char.isspace()}
    if not query_chars:
        return 0.0
    hits = sum(1 for char in query_chars if char in chunk)
    return hits / len(query_chars)


class MaterialContentRetriever:
    """基于会议材料解析文本的检索兜底实现（向量检索未落地时）。

    与 ``app.ai.chat.Retriever`` 协议同签名；待 M04 的 ``document_chunks`` /
    向量检索落地后，可由 agent 流以相同签名替换，无需改动 chat 路由。
    """

    def __init__(self, db: Session, user_id: str) -> None:
        self._db = db
        self._user_id = user_id

    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        meeting_id = current_meeting_id if scope == "current_meeting" else None
        rows = material_repository.list_content_rows(
            self._db, user_id, meeting_id=meeting_id
        )
        scored: list[RetrievedChunk] = []
        for row in rows:
            for excerpt in _split_chunks(row.content or ""):
                score = _score(query, excerpt)
                if score >= min_score:
                    scored.append(
                        RetrievedChunk(
                            meeting_id=row.meeting_id,
                            material_id=row.material_id,
                            record_id=None,
                            excerpt=excerpt,
                            score=score,
                        )
                    )
        scored.sort(key=lambda chunk: chunk.score, reverse=True)
        return scored[:top_k]
