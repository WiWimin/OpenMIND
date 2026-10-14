from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope, ListData
from app.schemas.issue import (
    IssueExtractRequest,
    IssueExtractResult,
    IssueRead,
    IssueUpdate,
)
from app.services import issue_service
from app.utils.pagination import build_pagination

router = APIRouter(tags=["issues"])


def _to_read(issue: object) -> IssueRead:
    return IssueRead.from_model(issue)


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
    return Envelope(data=IssueExtractResult(items=[_to_read(issue) for issue in issues]))


@router.get(
    "/meetings/{meeting_id}/issues", response_model=Envelope[ListData[IssueRead]]
)
def list_issues(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[ListData[IssueRead]]:
    items, total = issue_service.list_issues(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
    data = ListData[IssueRead](
        items=[_to_read(issue) for issue in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


@router.patch("/issues/{issue_id}", response_model=Envelope[IssueRead])
def update_issue(
    issue_id: str,
    payload: IssueUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[IssueRead]:
    issue = issue_service.update_issue(db, issue_id, current_user.user_id, payload)
    return Envelope(data=_to_read(issue))
