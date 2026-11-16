"""持久化任务队列 worker：DB 队列 + 线程池，不引入 Redis/Celery。

职责：

- 以 `FOR UPDATE SKIP LOCKED` 认领到期的 `async_jobs`（PostgreSQL），
  多 worker 并存不会重复执行；
- 按 `job_type + payload` 重建任务体（闭包不可跨进程传递）；
- 可重试错误回到 `pending` 并指数退避，超过 `max_attempts` 落 `failed`；
- 周期回收僵尸任务（心跳缺失/超时）。

启动：`python -m app.worker`。`JOB_WORKER_ENABLED=false` 时直接退出，
API 进程仍按旧行为用 `BackgroundTasks` 执行任务。
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.ai import audit
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.repositories import job_repository
from app.services import job_service, job_tasks

logger = logging.getLogger(__name__)

# 僵尸任务回收间隔（秒）
_REAP_INTERVAL_S = 30.0


def _worker_id() -> str:
    return f"worker-{socket.gethostname()}-{os.getpid()}"


def _claim(worker_id: str) -> str | None:
    """认领一个到期任务，返回 job_id；无任务或失败返回 None。"""
    db = SessionLocal()
    try:
        job = job_service.claim_next(db, worker_id)
        return job.job_id if job is not None else None
    except Exception:  # noqa: BLE001 — 认领失败不应终止 worker
        logger.exception("任务认领失败")
        db.rollback()
        return None
    finally:
        db.close()


def _retry_or_fail(
    db: Session, job_id: str, error_code: str, error_message: str
) -> None:
    try:
        db.rollback()
        job = job_repository.get(db, job_id)
        if job is not None:
            job_service.retry_or_fail(db, job, error_code, error_message)
    except Exception:  # noqa: BLE001 — 状态写入失败只告警
        logger.exception("任务失败状态写入异常 job_id=%s", job_id)


def _execute(job_id: str) -> None:
    """在独立会话中执行已认领任务，并统一状态流转。"""
    db = SessionLocal()
    token = None
    try:
        job = job_repository.get(db, job_id)
        if job is None:
            logger.error("任务不存在，跳过执行 job_id=%s", job_id)
            return
        if job.status != job_service.RUNNING:
            logger.warning(
                "任务状态非 running，跳过执行 job_id=%s status=%s",
                job_id,
                job.status,
            )
            return
        token = audit.bind_job(job.job_id)
        fn = job_tasks.build_job_fn(
            job_type=job.job_type,
            resource_id=job.resource_id,
            payload=job.payload or {},
            user_id=job.user_id,
        )

        def _progress(value: int) -> None:
            job_service.update_progress(db, job, value)
            # 进度回调顺带心跳，避免长任务被回收
            job_service.heartbeat(db, job)

        fn(db, _progress)
        job_service.mark_succeeded(db, job)
    except AppError as exc:
        _retry_or_fail(db, job_id, exc.error_code, exc.message)
    except Exception:  # noqa: BLE001 — 未知异常归一为可重试
        logger.exception("任务执行异常 job_id=%s", job_id)
        _retry_or_fail(db, job_id, "INTERNAL_ERROR", "任务执行失败")
    finally:
        if token is not None:
            audit.unbind_job(token)
        db.close()


def _reap() -> None:
    db = SessionLocal()
    try:
        count = job_service.reap_stale(db)
        if count:
            logger.warning("回收超时任务 count=%s", count)
    except Exception:  # noqa: BLE001
        logger.exception("回收超时任务失败")
        db.rollback()
    finally:
        db.close()


def run_worker(stop_event: threading.Event | None = None) -> None:
    settings = get_settings()
    if not settings.job_worker_enabled:
        logger.info("JOB_WORKER_ENABLED=false，worker 不启动")
        return

    worker_id = _worker_id()
    concurrency = max(1, settings.job_worker_concurrency)
    poll = max(0.1, settings.job_worker_poll_seconds)
    stop = stop_event or threading.Event()
    executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="job")
    futures: set[Future] = set()
    last_reap = 0.0
    logger.info("任务 worker 启动 id=%s concurrency=%s", worker_id, concurrency)

    try:
        while not stop.is_set():
            now = time.monotonic()
            if now - last_reap >= _REAP_INTERVAL_S:
                _reap()
                last_reap = now

            futures = {future for future in futures if not future.done()}
            if len(futures) >= concurrency:
                stop.wait(poll)
                continue

            job_id = _claim(worker_id)
            if job_id is None:
                stop.wait(poll)
                continue
            futures.add(executor.submit(_execute, job_id))
    finally:
        logger.info("任务 worker 停止中 id=%s", worker_id)
        executor.shutdown(wait=True)
        logger.info("任务 worker 已停止 id=%s", worker_id)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop = threading.Event()

    def _handle(*_args: object) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):  # pragma: no cover — 非主线程/平台差异
            pass

    run_worker(stop)


if __name__ == "__main__":
    main()
