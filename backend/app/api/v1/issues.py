from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.common import Envelope, ListData
from app.schemas.issue import (
    IssueExtractRequest,
    IssueExtractResult,
    IssueRead,
    IssueUpdate,
)
from app.services import issue_service

router = APIRouter(tags=["issues"])


@router.post(
    "/meetings/{meeting_id}/issues/extract",
    response_model=Envelope[IssueExtractResult],
)
def extract_issues(
    meeting_id: str,
    payload: IssueExtractRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[IssueExtractResult]:
    issues = issue_service.extract_issues(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        record_ids=payload.record_ids,
    )
    return Envelope(
        data=IssueExtractResult(items=[IssueRead.model_validate(issue) for issue in issues])
    )


@router.get(
    "/meetings/{meeting_id}/issues", response_model=Envelope[ListData[IssueRead]]
)
def list_issues(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[IssueRead]]:
    items, total = issue_service.list_issues(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, IssueRead, page=params.page, page_size=params.page_size, total=total
    )


@router.patch("/issues/{issue_id}", response_model=Envelope[IssueRead])
def update_issue(
    issue_id: str,
    payload: IssueUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[IssueRead]:
    issue = issue_service.update_issue(db, issue_id, current_user.user_id, payload)
    return Envelope(data=IssueRead.model_validate(issue))
