from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.task import PersonalTask
from app.repositories import task_repository
from app.schemas.task import TaskStatus, TaskUpdate

_TODO = "todo"
_IN_PROGRESS = "in_progress"
_COMPLETED = "completed"
_CANCELLED = "cancelled"

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    _TODO: {_IN_PROGRESS, _COMPLETED, _CANCELLED},
    _IN_PROGRESS: {_COMPLETED, _CANCELLED},
    _COMPLETED: set(),
    _CANCELLED: set(),
}


def _not_found() -> AppError:
    return AppError("RESOURCE_NOT_FOUND", "任务不存在或不可访问", http_status=404)


def list_tasks(
    db: Session, *, user_id: str, status: str | None, page: int, page_size: int
) -> tuple[list[PersonalTask], int]:
    offset = (page - 1) * page_size
    items = task_repository.list_by_user(
        db, user_id, status=status, limit=page_size, offset=offset
    )
    total = task_repository.count_by_user(db, user_id, status=status)
    return items, total


def get_owned_task(db: Session, task_id: str, user_id: str) -> PersonalTask:
    task = task_repository.get_owned(db, task_id, user_id)
    if task is None:
        raise _not_found()
    return task


def _ensure_transition(current: str, target: str) -> None:
    if target == current:
        return
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            f"不允许的状态流转：{current} → {target}",
            http_status=409,
        )


def update_task(
    db: Session, task_id: str, user_id: str, payload: TaskUpdate
) -> PersonalTask:
    task = get_owned_task(db, task_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("title") is not None:
        task.title = data["title"]
    if "due_date" in data:
        task.due_date = data["due_date"]
    if data.get("status") is not None:
        target = TaskStatus(data["status"]).value
        _ensure_transition(task.status, target)
        task.status = target
    return task_repository.update(db, task)


def cancel_task(db: Session, task_id: str, user_id: str) -> PersonalTask:
    task = get_owned_task(db, task_id, user_id)
    if task.status == _CANCELLED:
        return task
    if task.status == _COMPLETED:
        raise AppError("BUSINESS_RULE_VIOLATION", "已完成任务不可取消", http_status=409)
    task.status = _CANCELLED
    return task_repository.update(db, task)
