from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.audio import AudioDeleteResult, AudioRead, AudioUpdate
from app.schemas.common import Envelope, ListData
from app.services import audio_service
from app.utils.pagination import build_pagination

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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Envelope[ListData[AudioRead]]:
    items, total = audio_service.list_audio(
        db,
        meeting_id=meeting_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
    data = ListData[AudioRead](
        items=[AudioRead.model_validate(item) for item in items],
        pagination=build_pagination(page, page_size, total),
    )
    return Envelope(data=data)


@router.get("/audio/{audio_id}", response_model=Envelope[AudioRead])
def get_audio(
    audio_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[AudioRead]:
    audio = audio_service.get_owned_audio(
        db, audio_id, current_user.user_id
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
