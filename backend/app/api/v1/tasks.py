from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.common import Envelope, ListData
from app.schemas.task import TaskCreate, TaskRead, TaskStatus, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=Envelope[TaskRead]
)
def create_task(
    payload: TaskCreate, db: DbSession, current_user: CurrentUser
) -> Envelope[TaskRead]:
    task = task_service.create_task(
        db,
        user_id=current_user.user_id,
        title=payload.title,
        due_date=payload.due_date,
        priority=payload.priority.value,
    )
    return Envelope(data=TaskRead.model_validate(task))


@router.get("", response_model=Envelope[ListData[TaskRead]])
def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
) -> Envelope[ListData[TaskRead]]:
    items, total = task_service.list_tasks(
        db,
        user_id=current_user.user_id,
        status=task_status.value if task_status else None,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, TaskRead, page=params.page, page_size=params.page_size, total=total
    )


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
