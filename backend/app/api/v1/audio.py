from __future__ import annotations

import mimetypes
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, DbSession, UploadSizeCheck
from app.api.page import PageParams, list_envelope
from app.core.config import get_settings
from app.schemas.audio import (
    AudioDeleteResult,
    AudioLiveStart,
    AudioRead,
    AudioSegmentMarkerUpdate,
    AudioUpdate,
)
from app.schemas.common import Envelope, ListData
from app.schemas.job import JobAccepted, JobRead
from app.services import audio_service, job_service, job_tasks

router = APIRouter(tags=["audio"])


def _read_with_size(audio) -> AudioRead:
    """读模型 + 原始文件大小（stat 计算），供本地同步估算下载量。"""
    return AudioRead.model_validate(audio).model_copy(
        update={"file_size": audio_service.file_size_of(audio)}
    )

# 异步受理：202 + 任务对象；关闭 ASYNC_JOBS_ENABLED 时走原同步逻辑
_ACCEPTED = status.HTTP_202_ACCEPTED


@router.post(
    "/meetings/{meeting_id}/audio",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[AudioRead] | Envelope[JobAccepted],
)
async def upload_audio(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    _size_check: UploadSizeCheck,
    background_tasks: BackgroundTasks,
    response: Response,
    file: Annotated[UploadFile, File()],
    client_op_id: Annotated[str | None, Form(max_length=64)] = None,
) -> Envelope[AudioRead] | Envelope[JobAccepted]:
    content = await file.read()
    file_name = file.filename or "audio"
    # 文稿（docx/txt）走同步解析导入（本地解析很快），不入 ASR 任务队列
    if get_settings().async_jobs_enabled and not audio_service.is_document_file(file_name):
        audio = audio_service.upload_audio(
            db,
            meeting_id=meeting_id,
            user_id=current_user.user_id,
            file_name=file_name,
            content=content,
            defer_processing=True,
            client_op_id=client_op_id,
        )
        job = job_service.enqueue(
            db,
            background_tasks,
            user_id=current_user.user_id,
            job_type="audio_transcribe",
            resource_type="audio",
            resource_id=audio.audio_id,
            fn=job_tasks.audio_transcribe(audio.audio_id, current_user.user_id),
            payload={"audio_id": audio.audio_id},
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    # 同步路径会调用 ASR 转写（长音频可达分钟级），放线程池避免阻塞事件循环
    audio = await run_in_threadpool(
        audio_service.upload_audio,
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        file_name=file_name,
        content=content,
        client_op_id=client_op_id,
    )
    return Envelope(data=_read_with_size(audio))


@router.get(
    "/meetings/{meeting_id}/audio",
    response_model=Envelope[ListData[AudioRead]],
)
def list_audio(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[AudioRead]]:
    items, total = audio_service.list_audio(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=params.page,
        page_size=params.page_size,
    )
    return list_envelope(
        items, AudioRead, page=params.page, page_size=params.page_size, total=total
    )


@router.get("/audio/{audio_id}", response_model=Envelope[AudioRead])
def get_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioRead]:
    audio = audio_service.get_owned_audio(
        db, audio_id, current_user.user_id
    )
    return Envelope(data=_read_with_size(audio))


@router.get("/audio/{audio_id}/download")
def download_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Response:
    """下载音频原始文件（本地工作区同步用）；只接受 id，不接受路径。"""
    audio = audio_service.get_owned_audio(db, audio_id, current_user.user_id)
    content = audio_service.read_audio_file(audio)
    media_type = mimetypes.guess_type(audio.file_name)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(audio.file_name)}"
        },
    )


# ============================ 实时录音：分片边录边转 ============================


@router.post(
    "/meetings/{meeting_id}/audio/live/start",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[AudioRead],
)
def start_live_audio(
    meeting_id: str,
    payload: AudioLiveStart,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[AudioRead]:
    audio = audio_service.start_live_session(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        file_type=payload.file_type,
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.post("/audio/{audio_id}/live/chunk", response_model=Envelope[AudioRead])
async def upload_live_chunk(
    audio_id: str,
    db: DbSession,
    current_user: CurrentUser,
    _size_check: UploadSizeCheck,
    file: Annotated[UploadFile, File()],
    seq: Annotated[int, Form(ge=1)],
    offset_seconds: Annotated[int, Form(ge=0)] = 0,
) -> Envelope[AudioRead]:
    content = await file.read()
    # 分片同步转写（可能秒级到十秒级），放线程池避免阻塞事件循环
    audio, _segment = await run_in_threadpool(
        audio_service.append_live_chunk,
        db,
        audio_id,
        current_user.user_id,
        seq=seq,
        offset_seconds=offset_seconds,
        content=content,
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.post("/audio/{audio_id}/live/finish", response_model=Envelope[AudioRead])
def finish_live_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioRead]:
    audio = audio_service.finish_live_session(
        db, audio_id, current_user.user_id
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.post("/audio/{audio_id}/segments/{seq}/retry", response_model=Envelope[AudioRead])
def retry_audio_segment(
    audio_id: str, seq: int, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioRead]:
    audio = audio_service.retry_live_segment(
        db, audio_id, current_user.user_id, seq
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.patch("/audio/{audio_id}/segments/marker", response_model=Envelope[AudioRead])
def mark_audio_segment(
    audio_id: str,
    payload: AudioSegmentMarkerUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[AudioRead]:
    audio = audio_service.set_segment_marker(
        db,
        audio_id,
        current_user.user_id,
        seq=payload.seq,
        marker_type=payload.marker_type,
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.patch("/audio/{audio_id}", response_model=Envelope[AudioRead])
def update_audio_transcript(
    audio_id: str,
    payload: AudioUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[AudioRead]:
    audio = audio_service.update_transcript(
        db, audio_id, current_user.user_id, payload.transcript
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.post(
    "/audio/{audio_id}/retry",
    response_model=Envelope[AudioRead] | Envelope[JobAccepted],
)
def retry_audio(
    audio_id: str,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    response: Response,
) -> Envelope[AudioRead] | Envelope[JobAccepted]:
    """重新转写：异步开启时返回 202 + 任务，关闭时同步转写返回 200。"""
    if get_settings().async_jobs_enabled:
        audio = audio_service.retry_transcription(
            db, audio_id, current_user.user_id, defer_processing=True
        )
        job = job_service.enqueue(
            db,
            background_tasks,
            user_id=current_user.user_id,
            job_type="audio_transcribe",
            resource_type="audio",
            resource_id=audio.audio_id,
            fn=job_tasks.audio_transcribe(audio.audio_id, current_user.user_id),
            payload={"audio_id": audio.audio_id},
        )
        response.status_code = _ACCEPTED
        return Envelope(data=JobAccepted(job=JobRead.model_validate(job)))
    audio = audio_service.retry_transcription(
        db, audio_id, current_user.user_id
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.post("/audio/{audio_id}/confirm", response_model=Envelope[AudioRead])
def confirm_audio(
    audio_id: str,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Envelope[AudioRead]:
    audio = audio_service.confirm_audio(db, audio_id, current_user.user_id)
    return Envelope(data=AudioRead.model_validate(audio))


@router.delete("/audio/{audio_id}", response_model=Envelope[AudioDeleteResult])
def delete_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioDeleteResult]:
    audio_service.delete_audio(db, audio_id, current_user.user_id)
    return Envelope(data=AudioDeleteResult(audio_id=audio_id))
