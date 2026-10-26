from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.transcription import TranscriptionClient
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.audio import MeetingAudio
from app.repositories import audio_repository
from app.schemas.record import RecordCreate, RecordType
from app.services import meeting_service, record_service
from app.utils import storage
from app.utils.ids import new_id

ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "webm"}
_STATUS_UPLOADED = "uploaded"
_STATUS_PROCESSING = "processing"
_STATUS_TRANSCRIBED = "transcribed"
_STATUS_FAILED = "failed"
_STATUS_CONFIRMED = "confirmed"


def transcribe_file(content: bytes, file_name: str) -> str:
    return TranscriptionClient().transcribe(content, file_name)


def _infer_audio_type(file_name: str) -> str:
    candidate = Path(file_name).suffix.lower().lstrip(".")
    if candidate not in ALLOWED_AUDIO_EXTENSIONS:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的音频类型，仅支持 MP3、WAV、M4A、WEBM",
            http_status=415,
        )
    return candidate


def _run_transcription(
    db: Session, audio: MeetingAudio, content: bytes, file_name: str
) -> None:
    audio.status = _STATUS_PROCESSING
    audio.error = None
    db.commit()
    try:
        transcript = transcribe_file(content, file_name)
        audio.transcript = transcript
        audio.status = _STATUS_TRANSCRIBED
    except AppError as exc:
        audio.status = _STATUS_FAILED
        audio.error = exc.message
    except Exception:
        audio.status = _STATUS_FAILED
        audio.error = "音频转写失败"
    finally:
        db.commit()
        db.refresh(audio)


def upload_audio(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    file_name: str,
    content: bytes,
) -> MeetingAudio:
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    audio_type = _infer_audio_type(file_name)
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{settings.max_upload_mb}MB）",
            http_status=413,
        )

    audio_id = new_id("aud")
    storage_key = f"audio/{audio_id}.{audio_type}"
    storage.save_bytes(settings.storage_dir, relative_key=storage_key, data=content)
    try:
        audio = audio_repository.create(
            db,
            audio_id=audio_id,
            meeting_id=meeting_id,
            user_id=user_id,
            file_name=file_name,
            audio_type=audio_type,
            storage_key=storage_key,
        )
    except Exception:
        storage.delete_object(settings.storage_dir, storage_key)
        raise
    _run_transcription(db, audio, content, file_name)
    return audio


def list_audio(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[MeetingAudio], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    offset = (page - 1) * page_size
    items = audio_repository.list_by_meeting(
        db, meeting_id, limit=page_size, offset=offset
    )
    total = audio_repository.count_by_meeting(db, meeting_id)
    return items, total


def get_owned_audio(db: Session, audio_id: str, user_id: str) -> MeetingAudio:
    audio = audio_repository.get_owned(db, audio_id, user_id)
    if audio is None:
        raise AppError(
            "RESOURCE_NOT_FOUND", "音频不存在或不可访问", http_status=404
        )
    return audio


def retry_transcription(db: Session, audio_id: str, user_id: str) -> MeetingAudio:
    audio = get_owned_audio(db, audio_id, user_id)
    if audio.status == _STATUS_CONFIRMED:
        raise AppError(
            "BUSINESS_RULE_VIOLATION", "已确认的音频不能重新转写", http_status=409
        )
    meeting_service.get_mutable_meeting(db, audio.meeting_id, user_id)
    try:
        content = storage.read_bytes(get_settings().storage_dir, audio.storage_key)
    except OSError:
        raise AppError(
            "RESOURCE_NOT_FOUND", "音频文件不存在或不可访问", http_status=404
        ) from None
    _run_transcription(db, audio, content, audio.file_name)
    return audio


def update_transcript(
    db: Session, audio_id: str, user_id: str, transcript: str
) -> MeetingAudio:
    audio = get_owned_audio(db, audio_id, user_id)
    if audio.status == _STATUS_CONFIRMED:
        raise AppError(
            "BUSINESS_RULE_VIOLATION", "已确认的音频不能修改转写", http_status=409
        )
    meeting_service.get_mutable_meeting(db, audio.meeting_id, user_id)
    text = transcript.strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "转写文本不能为空", http_status=422)
    audio.transcript = text
    audio.status = _STATUS_TRANSCRIBED
    audio.error = None
    return audio_repository.update(db, audio)


def confirm_audio(db: Session, audio_id: str, user_id: str) -> MeetingAudio:
    audio = get_owned_audio(db, audio_id, user_id)
    if audio.record_id:
        return audio
    if audio.status != _STATUS_TRANSCRIBED or not audio.transcript:
        raise AppError(
            "VALIDATION_ERROR", "音频尚未成功转写", http_status=422
        )
    meeting_service.get_mutable_meeting(db, audio.meeting_id, user_id)
    record = record_service.create_record(
        db,
        meeting_id=audio.meeting_id,
        user_id=user_id,
        payload=RecordCreate(
            content=audio.transcript,
            record_type=RecordType.transcript,
        ),
    )
    audio.record_id = record.record_id
    audio.status = _STATUS_CONFIRMED
    return audio_repository.update(db, audio)


def delete_audio(db: Session, audio_id: str, user_id: str) -> None:
    audio = get_owned_audio(db, audio_id, user_id)
    if audio.record_id:
        raise AppError(
            "BUSINESS_RULE_VIOLATION",
            "已确认的音频已生成会议记录，不能删除",
            http_status=409,
        )
    meeting_service.get_mutable_meeting(db, audio.meeting_id, user_id)
    storage.delete_object(get_settings().storage_dir, audio.storage_key)
    audio_repository.delete(db, audio)
