"""行动项 / 问题 / 纪要抽取流程共用的记录收集与候选溯源工具。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.record import MeetingRecord
from app.repositories import record_repository

MAX_RECORDS = 100


def gather_records(
    db: Session, meeting_id: str, record_ids: list[str]
) -> list[MeetingRecord]:
    """按指定 id 收集记录；未指定时取最近 MAX_RECORDS 条。"""
    if record_ids:
        return record_repository.list_by_ids(db, meeting_id, record_ids)
    return record_repository.list_by_meeting(db, meeting_id, limit=MAX_RECORDS, offset=0)


def build_transcripts(records: list[MeetingRecord]) -> list[str]:
    """把记录格式化为抽取模型输入的 `[record_id] content` 文本序列。"""
    return [f"[{record.record_id}] {record.content}" for record in records]
