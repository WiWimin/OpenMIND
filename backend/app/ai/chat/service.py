from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.ai.llm import LLMClient
from app.ai.prompts import build_chat, build_deliverable, build_web_chat
from app.ai.websearch import WebResult, web_search
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 联网回答的前缀告知（两段式第一段）
_WEB_NOTICE = "你的会议资料中未找到相关证据。以下回答基于联网检索，仅供参考："


class BuildDeliverable(BaseModel):
    """Build 模式的结构化产出（chat_json schema）。"""

    summary: str = Field(description="给用户的简短说明（1-3 句）")
    filename: str = Field(description="文件名（不含路径，建议 .md 后缀）")
    content_md: str = Field(description="文件正文，Markdown 格式")


@dataclass(frozen=True)
class RecordContext:
    meeting_id: str
    record_id: str
    content: str


@dataclass(frozen=True)
class Source:
    meeting_id: str | None
    material_id: str | None
    record_id: str | None
    excerpt: str
    document_id: str | None = None
    document_name: str | None = None
    # 来源类别：material（材料/知识库）| record（会议记录）| web（联网检索）
    origin: str = "material"
    url: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class FileAttachment:
    filename: str
    content_md: str


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    sources: list[Source]
    insufficient_evidence: bool
    file: FileAttachment | None = None


class Retriever(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[Any]: ...


class ChatService:
    def __init__(self, llm: LLMClient, retriever: Retriever) -> None:
        self.llm = llm
        self.retriever = retriever

    def answer(
        self,
        question: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        records: list[RecordContext] | None = None,
        memory_context: str = "",
        mode: str = "plan",
    ) -> ChatAnswer:
        chunks = self.retriever.retrieve(
            question,
            user_id=user_id,
            scope=scope,
            current_meeting_id=current_meeting_id,
        )
        record_context = [] if scope == "knowledge_base" else (records or [])
        if not chunks and not record_context:
            return self._answer_with_web(question)
        contexts = [chunk.excerpt for chunk in chunks]
        contexts.extend(
            f"[记录 {record.record_id}] {record.content}" for record in record_context
        )
        attachment: FileAttachment | None = None
        if mode == "build":
            # Build：基于资料直接产出可交付文件（结构化输出），summary 作为回答
            deliverable = self.llm.chat_json(
                build_deliverable(
                    {
                        "question": question,
                        "contexts": contexts,
                        "memory_context": memory_context,
                    }
                ),
                schema=BuildDeliverable,
            )
            answer = deliverable.summary
            attachment = FileAttachment(
                filename=deliverable.filename,
                content_md=deliverable.content_md,
            )
        else:
            messages = build_chat(
                {
                    "question": question,
                    "contexts": contexts,
                    "memory_context": memory_context,
                }
            )
            answer = self.llm.chat(messages).text
        sources = [
            Source(
                meeting_id=chunk.meeting_id,
                material_id=chunk.material_id,
                record_id=chunk.record_id,
                excerpt=chunk.excerpt,
                document_id=getattr(chunk, "document_id", None),
                document_name=getattr(chunk, "document_name", None),
            )
            for chunk in chunks
        ]
        sources.extend(
            Source(
                meeting_id=record.meeting_id,
                material_id=None,
                record_id=record.record_id,
                excerpt=record.content[:500],
            )
            for record in record_context
        )
        return ChatAnswer(
            answer=answer, sources=sources, insufficient_evidence=False, file=attachment
        )

    def _answer_with_web(self, question: str) -> ChatAnswer:
        """资料无证据 → 两段式联网补救（答案层，不进入检索层）。

        联网关闭/无结果/失败一律回退既有拒答文案，绝不裸报错。
        """
        refusal = ChatAnswer(
            answer="根据现有材料无法确认该问题的答案。",
            sources=[],
            insufficient_evidence=True,
        )
        results: list[WebResult] = web_search(question)
        if not results:
            return refusal
        numbered = [
            {"title": item.title, "url": item.url, "snippet": item.snippet}
            for item in results
        ]
        messages = build_web_chat({"question": question, "sources": numbered})
        try:
            answer = self.llm.chat(messages).text
        except AppError as exc:  # 未配置/超时/额度 → 回退拒答，绝不裸报错
            logger.warning("联网回答 LLM 调用失败，回退拒答：%s", exc.error_code)
            return refusal
        except Exception as exc:  # noqa: BLE001
            logger.warning("联网回答异常，回退拒答：%s", type(exc).__name__)
            return refusal
        sources = [
            Source(
                meeting_id=None,
                material_id=None,
                record_id=None,
                excerpt=item.snippet or item.title[:200],
                origin="web",
                url=item.url,
                title=item.title,
            )
            for item in results
        ]
        return ChatAnswer(
            answer=f"{_WEB_NOTICE}\n\n{answer}",
            sources=sources,
            insufficient_evidence=True,
        )
