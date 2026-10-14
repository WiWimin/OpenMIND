from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Envelope, ListData
from app.schemas.task import TaskRead, TaskStatus, TaskUpdate
from app.services import task_service
from app.utils.pagination import build_pagination

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=Envelope[ListData[TaskRead]])
def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
) -> Envelope[ListData[TaskRead]]:
    items, total = task_service.list_tasks(
        db,
        user_id=current_user.user_id,
        status=task_status.value if task_status else None,
        page=page,
        page_size=page_size,
    )
    data = ListData[TaskRead](
        items=[TaskRead.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


@router.get("/{task_id}", response_model=Envelope[TaskRead])
def get_task(
    task_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[TaskRead]:
    task = task_service.get_owned_task(db, task_id, current_user.user_id)
    return Envelope(data=TaskRead.model_validate(task))


@router.patch("/{task_id}", response_model=Envelope[TaskRead])
def update_task(
    task_id: str, payload: TaskUpdate, db: DbSession, current_user: CurrentUser
) -> Envelope[TaskRead]:
    task = task_service.update_task(db, task_id, current_user.user_id, payload)
    return Envelope(data=TaskRead.model_validate(task))


@router.post("/{task_id}/cancel", response_model=Envelope[TaskRead])
def cancel_task(
    task_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[TaskRead]:
    task = task_service.cancel_task(db, task_id, current_user.user_id)
    return Envelope(data=TaskRead.model_validate(task))
