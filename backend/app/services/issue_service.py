from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.extraction import IssueCandidate, IssueExtractor
from app.core.exceptions import AppError
from app.models.issue import OpenIssue
from app.repositories import issue_repository, record_repository
from app.schemas.issue import IssueStatus, IssueUpdate
from app.services import meeting_service
from app.services.model_config_service import (
    ModelConfig,
    build_llm_client,
    resolve_model_config,
)
from app.utils.ids import new_id

_STATUS_OPEN = "open"
_MAX_RECORDS = 100


def extract_candidates(transcripts: list[str], config: ModelConfig) -> list[IssueCandidate]:
    return IssueExtractor(build_llm_client(config)).extract(transcripts)


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "问题不存在或不可访问", http_status=404)


def _gather_transcripts(db: Session, meeting_id: str, record_ids: list[str]) -> list[str]:
    if record_ids:
        records = record_repository.list_by_ids(db, meeting_id, record_ids)
    else:
        records = record_repository.list_by_meeting(
            db, meeting_id, limit=_MAX_RECORDS, offset=0
        )
    return [record.content for record in records]


def extract_issues(
    db: Session, *, meeting_id: str, user_id: str, record_ids: list[str]
) -> list[OpenIssue]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    transcripts = _gather_transcripts(db, meeting_id, record_ids)
    config = resolve_model_config(db, user_id)
    candidates = extract_candidates(transcripts, config)
    issues: list[OpenIssue] = []
    for candidate in candidates:
        issues.append(
            issue_repository.create(
                db,
                issue_id=new_id("iss"),
                meeting_id=meeting_id,
                description=candidate.description,
                follow_up=candidate.follow_up,
                source_record_id=candidate.source_record_id,
                status=_STATUS_OPEN,
            )
        )
    return issues


def list_issues(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[OpenIssue], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = issue_repository.list_by_meeting(db, meeting_id, limit=page_size, offset=offset)
    total = issue_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_issue(db: Session, issue_id: str, user_id: str) -> OpenIssue:
    issue = issue_repository.get_owned(db, issue_id, user_id)
    if issue is None:
        raise _not_found()
    return issue


def update_issue(
    db: Session, issue_id: str, user_id: str, payload: IssueUpdate
) -> OpenIssue:
    issue = get_owned_issue(db, issue_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("description") is not None:
        issue.description = data["description"]
    if "follow_up" in data:
        issue.follow_up = data["follow_up"]
    if data.get("status") is not None:
        issue.status = IssueStatus(data["status"]).value
    return issue_repository.update(db, issue)
