from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, resource_not_found
from app.models.task import PersonalTask
from app.repositories import meeting_repository, task_repository
from app.schemas.task import TaskPriority, TaskStatus, TaskUpdate
from app.utils.ids import new_id
from app.utils.pagination import paginate_by

_TODO = "todo"
_IN_PROGRESS = "in_progress"
_COMPLETED = "completed"
_CANCELLED = "cancelled"

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    _TODO: {_IN_PROGRESS, _COMPLETED, _CANCELLED},
    _IN_PROGRESS: {_TODO, _COMPLETED, _CANCELLED},
    # 已完成任务可撤回到待办（归档页「撤回」）；已取消任务保持终态
    _COMPLETED: {_TODO},
    _CANCELLED: set(),
}


def list_tasks(
    db: Session, *, user_id: str, status: str | None, page: int, page_size: int
) -> tuple[list[PersonalTask], int]:
    items, total = paginate_by(
        task_repository.list_by_user,
        task_repository.count_by_user,
        db,
        user_id,
        page=page,
        page_size=page_size,
        status=status,
    )
    # 附带关联会议标题（表格跳转链接展示），批量一次查询
    meeting_ids = [task.meeting_id for task in items if task.meeting_id]
    titles = meeting_repository.titles_by_ids(db, user_id, meeting_ids)
    for task in items:
        task.meeting_title = titles.get(task.meeting_id) if task.meeting_id else None
    return items, total


def create_task(
    db: Session,
    *,
    user_id: str,
    title: str,
    due_date: date | None,
    priority: str = TaskPriority.medium.value,
) -> PersonalTask:
    return task_repository.create(
        db,
        task_id=new_id("tsk"),
        user_id=user_id,
        meeting_id=None,
        action_id=None,
        title=title,
        due_date=due_date,
        priority=priority,
    )


def get_owned_task(db: Session, task_id: str, user_id: str) -> PersonalTask:
    task = task_repository.get_owned(db, task_id, user_id)
    if task is None:
        raise resource_not_found("任务")
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
    if data.get("priority") is not None:
        task.priority = TaskPriority(data["priority"]).value
    return task_repository.update(db, task)


def cancel_task(db: Session, task_id: str, user_id: str) -> PersonalTask:
    task = get_owned_task(db, task_id, user_id)
    if task.status == _CANCELLED:
        return task
    if task.status == _COMPLETED:
        raise AppError("BUSINESS_RULE_VIOLATION", "已完成任务不可取消", http_status=409)
    task.status = _CANCELLED
    return task_repository.update(db, task)
