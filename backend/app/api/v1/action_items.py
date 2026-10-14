from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
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
from app.utils.pagination import build_pagination

router = APIRouter(tags=["action-items"])


def _to_read(item: object) -> ActionItemRead:
    return ActionItemRead.from_model(item)


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
    return Envelope(data=ActionItemExtractResult(items=[_to_read(item) for item in items]))


@router.get(
    "/meetings/{meeting_id}/action-items",
    response_model=Envelope[ListData[ActionItemRead]],
)
def list_action_items(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[ListData[ActionItemRead]]:
    items, total = action_item_service.list_action_items(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
    data = ListData[ActionItemRead](
        items=[_to_read(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


@router.get("/action-items/{action_id}", response_model=Envelope[ActionItemRead])
def get_action_item(
    action_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[ActionItemRead]:
    item = action_item_service.get_owned_action_item(db, action_id, current_user.user_id)
    return Envelope(data=_to_read(item))


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
    return Envelope(data=_to_read(item))


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
    return Envelope(data=_to_read(item))


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
