from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.audio import (
    AudioDeleteResult,
    AudioLiveStart,
    AudioRead,
    AudioSegmentMarkerUpdate,
    AudioUpdate,
)
from app.schemas.common import Envelope, ListData
from app.services import audio_service

router = APIRouter(tags=["audio"])


@router.post(
    "/meetings/{meeting_id}/audio",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[AudioRead],
)
async def upload_audio(
    meeting_id: str,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> Envelope[AudioRead]:
    content = await file.read()
    audio = audio_service.upload_audio(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        file_name=file.filename or "audio",
        content=content,
    )
    return Envelope(data=AudioRead.model_validate(audio))


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
    return Envelope(data=AudioRead.model_validate(audio))


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
    file: Annotated[UploadFile, File()],
    seq: Annotated[int, Form(ge=1)],
    offset_seconds: Annotated[int, Form(ge=0)] = 0,
) -> Envelope[AudioRead]:
    content = await file.read()
    audio, _segment = audio_service.append_live_chunk(
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


@router.post("/audio/{audio_id}/retry", response_model=Envelope[AudioRead])
def retry_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioRead]:
    audio = audio_service.retry_transcription(
        db, audio_id, current_user.user_id
    )
    return Envelope(data=AudioRead.model_validate(audio))


@router.post("/audio/{audio_id}/confirm", response_model=Envelope[AudioRead])
def confirm_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioRead]:
    audio = audio_service.confirm_audio(db, audio_id, current_user.user_id)
    return Envelope(data=AudioRead.model_validate(audio))


@router.delete("/audio/{audio_id}", response_model=Envelope[AudioDeleteResult])
def delete_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioDeleteResult]:
    audio_service.delete_audio(db, audio_id, current_user.user_id)
    return Envelope(data=AudioDeleteResult(audio_id=audio_id))
