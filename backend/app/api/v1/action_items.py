from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.action_item import (
    ActionItemExtractRequest,
    ActionItemExtractResult,
    ActionItemRead,
    ActionItemUpdate,
    ConvertToTaskRequest,
)
from app.schemas.common import ActionItemDeleteResult, Envelope, ListData
from app.schemas.task import TaskRead
from app.services import action_item_service

router = APIRouter(tags=["action-items"])


@router.post(
    "/meetings/{meeting_id}/action-items/extract",
    response_model=Envelope[ActionItemExtractResult],
)
def extract_action_items(
    meeting_id: str,
    payload: ActionItemExtractRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[ActionItemExtractResult]:
    items = action_item_service.extract_action_items(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        record_ids=payload.record_ids,
    )
    return Envelope(
        data=ActionItemExtractResult(
            items=[ActionItemRead.model_validate(item) for item in items]
        )
    )


@router.get(
    "/meetings/{meeting_id}/action-items",
    response_model=Envelope[ListData[ActionItemRead]],
)
def list_action_items(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[ActionItemRead]]:
    items, total = action_item_service.list_action_items(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, ActionItemRead, page=params.page, page_size=params.page_size, total=total
    )


@router.get("/action-items/{action_id}", response_model=Envelope[ActionItemRead])
def get_action_item(
    action_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[ActionItemRead]:
    item = action_item_service.get_owned_action_item(db, action_id, current_user.user_id)
    return Envelope(data=ActionItemRead.model_validate(item))


@router.patch("/action-items/{action_id}", response_model=Envelope[ActionItemRead])
def update_action_item(
    action_id: str,
    payload: ActionItemUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[ActionItemRead]:
    item = action_item_service.update_action_item(
        db, action_id, current_user.user_id, payload
    )
    return Envelope(data=ActionItemRead.model_validate(item))


@router.delete(
    "/action-items/{action_id}", response_model=Envelope[ActionItemDeleteResult]
)
def delete_action_item(
    action_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[ActionItemDeleteResult]:
    action_item_service.delete_action_item(db, action_id, current_user.user_id)
    return Envelope(data=ActionItemDeleteResult(action_id=action_id))


@router.post("/action-items/{action_id}/confirm", response_model=Envelope[ActionItemRead])
def confirm_action_item(
    action_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[ActionItemRead]:
    item = action_item_service.confirm_action_item(db, action_id, current_user.user_id)
    return Envelope(data=ActionItemRead.model_validate(item))


@router.post(
    "/action-items/{action_id}/convert-to-task", response_model=Envelope[TaskRead]
)
def convert_to_task(
    action_id: str,
    payload: ConvertToTaskRequest,
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
) -> Envelope[TaskRead]:
    task, created = action_item_service.convert_to_task(
        db, action_id=action_id, user_id=current_user.user_id, payload=payload
    )
    if created:
        response.status_code = status.HTTP_201_CREATED
    return Envelope(data=TaskRead.model_validate(task))
