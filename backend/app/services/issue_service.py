from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai import audit
from app.ai.extraction import IssueCandidate, IssueExtractor
from app.core.exceptions import AppError, resource_not_found
from app.models.issue import OpenIssue
from app.models.record import MeetingRecord
from app.repositories import issue_repository
from app.schemas.issue import IssueCreate, IssueStatus, IssueUpdate
from app.services import ai_audit_service, meeting_service, sync_support
from app.services.extraction_support import build_transcripts, gather_records
from app.services.model_config_service import (
    ModelConfig,
    ModelPurpose,
    build_llm_client,
    resolve_model_config,
)
from app.utils.ids import new_id
from app.utils.pagination import paginate_by

_STATUS_OPEN = "open"
_STATUS_RESOLVED = "resolved"
_STATUS_CANCELLED = "cancelled"

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    _STATUS_OPEN: {_STATUS_RESOLVED, _STATUS_CANCELLED},
    _STATUS_RESOLVED: set(),
    _STATUS_CANCELLED: set(),
}


def extract_candidates(transcripts: list[str], config: ModelConfig) -> list[IssueCandidate]:
    return IssueExtractor(build_llm_client(config)).extract(transcripts)


def _source_record_id(
    records: list[MeetingRecord], candidate: IssueCandidate
) -> str | None:
    valid_ids = {record.record_id for record in records}
    if candidate.source_record_id is None:
        return records[0].record_id if len(records) == 1 else None
    if candidate.source_record_id in valid_ids:
        return candidate.source_record_id
    return None


def extract_issues(
    db: Session, *, meeting_id: str, user_id: str, record_ids: list[str]
) -> list[OpenIssue]:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    records = gather_records(db, meeting_id, record_ids)
    transcripts = build_transcripts(records)
    config = resolve_model_config(db, user_id, purpose=ModelPurpose.extraction)
    with ai_audit_service.audit_call(
        db,
        user_id=user_id,
        scene="extract_issues",
        model=config.llm_model,
        provider=audit.provider_host(config.llm_api_base),
    ):
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
                source_record_id=_source_record_id(records, candidate),
                status=_STATUS_OPEN,
            )
        )
    return issues


def create_issue(
    db: Session, *, meeting_id: str, user_id: str, payload: IssueCreate
) -> OpenIssue:
    """手工新建问题（本地工作区导入）；来源记录留空，状态固定 open。"""
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    if payload.client_op_id:
        existing = issue_repository.get_by_client_op_id(db, payload.client_op_id)
        if existing is not None:
            if existing.meeting_id != meeting_id:
                raise resource_not_found("问题")
            sync_support.ensure_same_payload(
                {
                    "description": existing.description,
                    "follow_up": existing.follow_up,
                },
                {"description": payload.description, "follow_up": payload.follow_up},
            )
            return existing
    return issue_repository.create(
        db,
        issue_id=new_id("iss"),
        meeting_id=meeting_id,
        description=payload.description,
        follow_up=payload.follow_up,
        source_record_id=None,
        status=_STATUS_OPEN,
        client_op_id=payload.client_op_id,
    )


def list_issues(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[OpenIssue], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    return paginate_by(
        issue_repository.list_by_meeting,
        issue_repository.count_by_meeting,
        db,
        meeting_id,
        page=page,
        page_size=page_size,
    )


def get_owned_issue(db: Session, issue_id: str, user_id: str) -> OpenIssue:
    issue = issue_repository.get_owned(db, issue_id, user_id)
    if issue is None:
        raise resource_not_found("问题")
    return issue


def update_issue(
    db: Session, issue_id: str, user_id: str, payload: IssueUpdate
) -> OpenIssue:
    issue = get_owned_issue(db, issue_id, user_id)
    meeting_service.get_mutable_meeting(db, issue.meeting_id, user_id)
    # 乐观锁：本地同步回写前校验远端未被修改，避免覆盖他人修改
    sync_support.ensure_unmodified(
        issue.updated_at, payload.expected_updated_at, label="问题"
    )
    data = payload.model_dump(exclude_unset=True, exclude={"expected_updated_at"})
    if data.get("description") is not None:
        issue.description = data["description"]
    if "follow_up" in data:
        issue.follow_up = data["follow_up"]
    if data.get("status") is not None:
        target = IssueStatus(data["status"]).value
        if target != issue.status and target not in _ALLOWED_TRANSITIONS.get(
            issue.status, set()
        ):
            raise AppError(
                "BUSINESS_RULE_VIOLATION",
                f"不允许的状态流转：{issue.status} → {target}",
                http_status=409,
            )
        issue.status = target
    return issue_repository.update(db, issue)
