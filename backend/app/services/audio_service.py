from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.transcription import TranscriptionClient
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.audio import MeetingAudio
from app.repositories import audio_repository
from app.schemas.record import RecordCreate, RecordMarkerType, RecordType
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
        _resplit_segments(audio, transcript)
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


# ============================ 实时录音：分片边录边转 ============================


def _live_file_name(ext: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"实时录音-{stamp}.{ext}"


def _chunk_key(audio_id: str, seq: int, ext: str) -> str:
    return f"audio/{audio_id}/chunks/{seq:04d}.{ext}"


def _ensure_mutable(db: Session, audio: MeetingAudio, user_id: str) -> None:
    meeting_service.get_mutable_meeting(db, audio.meeting_id, user_id)


def _transcribe_chunk(content: bytes, ext: str, seq: int) -> str:
    return transcribe_file(content, f"chunk-{seq:04d}.{ext}")


def _rebuild_transcript(audio: MeetingAudio) -> None:
    parts = [seg["text"] for seg in audio.segments or [] if seg.get("text")]
    audio.transcript = "\n".join(parts) if parts else None


def start_live_session(
    db: Session, *, meeting_id: str, user_id: str, file_type: str = "webm"
) -> MeetingAudio:
    """录音开始：创建一条 processing 状态的音频记录，后续分片追加到该记录。"""
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    ext = file_type.lower().lstrip(".")
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的音频类型，仅支持 MP3、WAV、M4A、WEBM",
            http_status=415,
        )
    audio_id = new_id("aud")
    return audio_repository.create(
        db,
        audio_id=audio_id,
        meeting_id=meeting_id,
        user_id=user_id,
        file_name=_live_file_name(ext),
        audio_type=ext,
        storage_key=f"audio/{audio_id}/live.{ext}",
        status=_STATUS_PROCESSING,
    )


def append_live_chunk(
    db: Session,
    audio_id: str,
    user_id: str,
    *,
    seq: int,
    offset_seconds: int,
    content: bytes,
) -> tuple[MeetingAudio, dict]:
    """上传一个分片：存盘 → 逐片转写 → 追加分段与全文。单片失败不中断整体。"""
    audio = get_owned_audio(db, audio_id, user_id)
    _ensure_mutable(db, audio, user_id)
    if audio.status != _STATUS_PROCESSING:
        raise AppError(
            "BUSINESS_RULE_VIOLATION", "该音频不在实时转写会话中", http_status=409
        )
    # 逐项浅拷贝：避免原地修改已加载的 JSON 值导致新旧值相等、UPDATE 被跳过
    segments = [dict(seg) for seg in (audio.segments or [])]
    if seq != len(segments) + 1:
        expected = len(segments) + 1
        raise AppError(
            "VALIDATION_ERROR",
            f"分片序号不连续，期望 {expected}，收到 {seq}",
            http_status=422,
        )
    if not content:
        raise AppError("VALIDATION_ERROR", "分片内容为空", http_status=422)
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"文件超过大小限制（{settings.max_upload_mb}MB）",
            http_status=413,
        )

    ext = audio.type
    chunk_key = _chunk_key(audio_id, seq, ext)
    storage.save_bytes(settings.storage_dir, relative_key=chunk_key, data=content)

    segment: dict = {
        "seq": seq,
        "offset_seconds": max(0, int(offset_seconds)),
        "text": "",
        "marker_type": None,
        "error": None,
    }
    try:
        segment["text"] = _transcribe_chunk(content, ext, seq)
    except AppError as exc:
        segment["error"] = exc.message
    except Exception:
        segment["error"] = "音频转写失败"

    segments.append(segment)
    audio.segments = segments
    _rebuild_transcript(audio)
    audio.error = None
    audio_repository.update(db, audio)
    return audio, segment


def finish_live_session(db: Session, audio_id: str, user_id: str) -> MeetingAudio:
    """录音结束：按序合并分片为主文件（幂等），并落定最终状态。"""
    audio = get_owned_audio(db, audio_id, user_id)
    _ensure_mutable(db, audio, user_id)
    if audio.status != _STATUS_PROCESSING:
        return audio

    settings = get_settings()
    ext = audio.type
    segments = list(audio.segments or [])
    merged = bytearray()
    for seg in segments:
        try:
            key = _chunk_key(audio_id, seg["seq"], ext)
            merged.extend(storage.read_bytes(settings.storage_dir, key))
        except OSError:
            continue

    if merged:
        final_key = f"audio/{audio_id}.{ext}"
        storage.save_bytes(settings.storage_dir, relative_key=final_key, data=bytes(merged))
        audio.storage_key = final_key
        for seg in segments:
            storage.delete_object(settings.storage_dir, _chunk_key(audio_id, seg["seq"], ext))
        storage.remove_tree(settings.storage_dir, f"audio/{audio_id}")

    if (audio.transcript or "").strip():
        audio.status = _STATUS_TRANSCRIBED
        audio.error = None
    else:
        audio.status = _STATUS_FAILED
        audio.error = "实时转写失败，未得到任何文本"
    return audio_repository.update(db, audio)


def set_segment_marker(
    db: Session, audio_id: str, user_id: str, *, seq: int, marker_type: str | None
) -> MeetingAudio:
    audio = get_owned_audio(db, audio_id, user_id)
    _ensure_mutable(db, audio, user_id)
    if marker_type is not None and marker_type not in {item.value for item in RecordMarkerType}:
        raise AppError("VALIDATION_ERROR", "未知的标记类型", http_status=422)
    # 逐项浅拷贝：避免原地修改已加载的 JSON 值导致新旧值相等、UPDATE 被跳过
    segments = [dict(seg) for seg in (audio.segments or [])]
    for seg in segments:
        if seg.get("seq") == seq:
            seg["marker_type"] = marker_type
            break
    else:
        raise AppError("RESOURCE_NOT_FOUND", "转写分段不存在", http_status=404)
    audio.segments = segments
    return audio_repository.update(db, audio)


def retry_live_segment(
    db: Session, audio_id: str, user_id: str, seq: int
) -> MeetingAudio:
    """对转写失败的分片重新转写（仅实时会话进行中可用，分片文件尚在）。"""
    audio = get_owned_audio(db, audio_id, user_id)
    _ensure_mutable(db, audio, user_id)
    if audio.status != _STATUS_PROCESSING:
        raise AppError(
            "BUSINESS_RULE_VIOLATION", "仅在实时转写会话中可重试分段", http_status=409
        )
    # 逐项浅拷贝：避免原地修改已加载的 JSON 值导致新旧值相等、UPDATE 被跳过
    segments = [dict(seg) for seg in (audio.segments or [])]
    target = next((seg for seg in segments if seg.get("seq") == seq), None)
    if target is None:
        raise AppError("RESOURCE_NOT_FOUND", "转写分段不存在", http_status=404)
    settings = get_settings()
    ext = audio.type
    try:
        content = storage.read_bytes(settings.storage_dir, _chunk_key(audio_id, seq, ext))
    except OSError:
        raise AppError(
            "RESOURCE_NOT_FOUND", "分片文件不存在或不可访问", http_status=404
        ) from None
    try:
        target["text"] = _transcribe_chunk(content, ext, seq)
        target["error"] = None
    except AppError as exc:
        target["error"] = exc.message
    except Exception:
        target["error"] = "音频转写失败"
    audio.segments = segments
    _rebuild_transcript(audio)
    return audio_repository.update(db, audio)


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


def _resplit_segments(audio: MeetingAudio, text: str) -> None:
    """用户编辑全文后按行重拆分段；沿用原分段的相对时间与标记。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    old = list(audio.segments or [])
    segments = []
    for index, line in enumerate(lines):
        base = old[index] if index < len(old) else {}
        segments.append(
            {
                "seq": index + 1,
                "offset_seconds": base.get("offset_seconds", 0),
                "text": line,
                "marker_type": base.get("marker_type"),
                "error": None,
            }
        )
    audio.segments = segments if segments else None


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
    _resplit_segments(audio, text)
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
    settings = get_settings()
    storage.delete_object(settings.storage_dir, audio.storage_key)
    for seg in audio.segments or []:
        storage.delete_object(settings.storage_dir, _chunk_key(audio_id, seg["seq"], audio.type))
    audio_repository.delete(db, audio)
