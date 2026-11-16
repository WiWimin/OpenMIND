from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai import audit
from app.ai.parsers.parser_service import parse_bytes
from app.ai.transcription import TranscriptionClient
from app.ai.transcription.client import (
    SCENE_ASR,
    SCENE_ASR_LIVE,
    probe_duration_seconds,
)
from app.core.config import get_settings
from app.core.exceptions import AppError, resource_not_found
from app.models.audio import MeetingAudio
from app.repositories import audio_repository
from app.schemas.record import RecordCreate, RecordMarkerType, RecordType
from app.services import ai_audit_service, meeting_service, record_service, sync_support
from app.utils import storage
from app.utils.ids import new_id
from app.utils.pagination import paginate_by
from app.utils.storage import ensure_upload_size

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "webm"}
# 用户已转写好的文稿（Word / 纯文本）：本地解析导入，不走 ASR
DOCUMENT_EXTENSIONS = {"docx", "txt"}
ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS
_STATUS_UPLOADED = "uploaded"
_STATUS_PROCESSING = "processing"
_STATUS_TRANSCRIBED = "transcribed"
_STATUS_FAILED = "failed"
_STATUS_CONFIRMED = "confirmed"


def transcribe_file(content: bytes, file_name: str) -> str:
    return TranscriptionClient().transcribe(content, file_name)


def _transcribe_audited(
    db: Session,
    *,
    user_id: str,
    scene: str,
    content: bytes,
    file_name: str,
    audit_enabled: bool = True,
) -> str:
    """转写一段音频并把元数据写入 `ai_call_logs`（`ai-design.md 3.11`）。

    - 审计是旁路：落库失败只告警并回滚该会话，转写结果照常返回；
    - 调用方须保证此时会话内**没有未提交的业务写入**（审计会提交一次）。
    """
    if not audit_enabled:
        return transcribe_file(content, file_name)
    settings = get_settings()
    with ai_audit_service.audit_call(
        db,
        user_id=user_id,
        scene=scene,
        model=settings.asr_model,
        provider=audit.provider_host(settings.asr_api_base),
    ):
        return transcribe_file(content, file_name)


def _ensure_duration_within_limit(content: bytes, file_name: str) -> None:
    """发送前的音频时长预检：超限直接拒绝，不打到 ASR。

    ffprobe 未安装或探测失败时跳过（回退到只按体积预检），不阻断正常上传。
    """
    limit = get_settings().asr_max_audio_seconds
    if limit <= 0:
        return
    duration = probe_duration_seconds(content, file_name)
    if duration is None or duration <= limit:
        return
    raise AppError(
        "VALIDATION_ERROR",
        f"音频时长超过上限（{limit // 60} 分钟）",
        http_status=422,
        retryable=False,
        details={"reason": "audio_too_long", "max_seconds": limit},
    )


def _infer_audio_type(file_name: str) -> str:
    candidate = Path(file_name).suffix.lower().lstrip(".")
    if candidate not in ALLOWED_UPLOAD_EXTENSIONS:
        raise AppError(
            "FILE_TYPE_NOT_SUPPORTED",
            "不支持的文件类型，仅支持 MP3、WAV、M4A、WEBM 音频或 DOCX、TXT 文稿",
            http_status=415,
        )
    return candidate


def is_document_file(file_name: str) -> bool:
    """是否为已转写好的文稿（docx/txt）——上传后直接解析导入。"""
    return Path(file_name).suffix.lower().lstrip(".") in DOCUMENT_EXTENSIONS


def _parse_document_text(content: bytes, file_name: str) -> str:
    """解析用户已转写好的文稿为纯文本；解析失败直接拒绝（不落记录）。

    本地解析（python-docx / 纯文本），无模型调用，不写 AI 审计。
    """
    parsed = parse_bytes(content, file_name)
    text = parsed.content.strip()
    if not text:
        raise AppError(
            "VALIDATION_ERROR",
            f"文稿内容为空：{Path(file_name).name}",
            http_status=422,
            retryable=False,
        )
    return text


def _run_transcription(
    db: Session,
    audio: MeetingAudio,
    content: bytes,
    file_name: str,
    *,
    progress_cb: Callable[[int], None] | None = None,
) -> str | None:
    """转写 + 分段：成功返回 `None`，失败落 `failed` 并返回错误码（供任务判定成败）。"""
    audio.status = _STATUS_PROCESSING
    audio.error = None
    db.commit()
    if progress_cb:
        progress_cb(10)
    error_code: str | None = None
    try:
        transcript = _transcribe_audited(
            db,
            user_id=audio.user_id,
            scene=SCENE_ASR,
            content=content,
            file_name=file_name,
        )
        if progress_cb:
            progress_cb(70)
        audio.transcript = transcript
        _resplit_segments(audio, transcript)
        audio.status = _STATUS_TRANSCRIBED
        if progress_cb:
            progress_cb(90)
    except AppError as exc:
        audio.status = _STATUS_FAILED
        audio.error = exc.message
        error_code = exc.error_code
    except Exception:
        logger.exception("音频转写失败 audio_id=%s", audio.audio_id)
        audio.status = _STATUS_FAILED
        audio.error = "音频转写失败"
        error_code = "INTERNAL_ERROR"
    finally:
        db.commit()
        db.refresh(audio)
    return error_code


def upload_audio(
    db: Session,
    *,
    meeting_id: str,
    user_id: str,
    file_name: str,
    content: bytes,
    defer_processing: bool = False,
    client_op_id: str | None = None,
) -> MeetingAudio:
    """上传音频或文稿。

    - 音频：同步或交由异步任务转写；`defer_processing=True` 只落盘建记录；
    - 文稿（docx/txt）：本地解析后直接写入转写结果，不调 ASR、不建任务。
    """
    meeting_service.get_mutable_meeting(db, meeting_id, user_id)
    audio_type = _infer_audio_type(file_name)
    settings = get_settings()
    ensure_upload_size(content, max_mb=settings.max_upload_mb)

    # 文稿先解析再落盘：解析失败直接拒绝，不留孤儿记录
    document_text: str | None = None
    if audio_type in DOCUMENT_EXTENSIONS:
        document_text = _parse_document_text(content, file_name)
    else:
        # 发送前预检：超长音频直接拒绝，避免占满 ASR 并发与任务队列
        _ensure_duration_within_limit(content, file_name)

    # 幂等键：同一 client_op_id 重复提交只落一条，避免同步重试重复转写
    if client_op_id:
        existing = audio_repository.get_by_client_op_id(db, client_op_id)
        if existing is not None:
            if existing.user_id != user_id or existing.meeting_id != meeting_id:
                raise resource_not_found("音频")
            sync_support.ensure_same_payload(
                {"file_name": existing.file_name, "type": existing.type},
                {"file_name": file_name, "type": audio_type},
            )
            return existing

    audio_id = new_id("aud")
    storage_key = f"audio/{audio_id}.{audio_type}"
    audio = storage.save_then_create(
        settings.storage_dir,
        storage_key,
        content,
        lambda: audio_repository.create(
            db,
            audio_id=audio_id,
            meeting_id=meeting_id,
            user_id=user_id,
            file_name=file_name,
            audio_type=audio_type,
            storage_key=storage_key,
            client_op_id=client_op_id,
        ),
    )
    if document_text is not None:
        # 已转写好的文稿：直接作为转写结果入库
        audio.transcript = document_text
        audio.status = _STATUS_TRANSCRIBED
        audio.error = None
        _resplit_segments(audio, document_text)
        db.commit()
        db.refresh(audio)
        return audio
    if not defer_processing:
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


def _transcribe_chunk(
    db: Session,
    user_id: str,
    content: bytes,
    ext: str,
    seq: int,
    *,
    audit_enabled: bool = True,
) -> str:
    return _transcribe_audited(
        db,
        user_id=user_id,
        scene=SCENE_ASR_LIVE,
        content=content,
        file_name=f"chunk-{seq:04d}.{ext}",
        audit_enabled=audit_enabled,
    )


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
    ensure_upload_size(content, max_mb=settings.max_upload_mb)

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
        segment["text"] = _transcribe_chunk(
            db,
            user_id,
            content,
            ext,
            seq,
            audit_enabled=settings.ai_audit_asr_chunks,
        )
    except AppError as exc:
        segment["error"] = exc.message
    except Exception:
        logger.exception(
            "实时转写分片失败 audio_id=%s seq=%d", audio_id, seq
        )
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
        target["text"] = _transcribe_chunk(
            db,
            user_id,
            content,
            ext,
            seq,
            audit_enabled=settings.ai_audit_asr_chunks,
        )
        target["error"] = None
    except AppError as exc:
        target["error"] = exc.message
    except Exception:
        logger.exception("实时转写分片重试失败 audio_id=%s seq=%s", audio_id, seq)
        target["error"] = "音频转写失败"
    audio.segments = segments
    _rebuild_transcript(audio)
    return audio_repository.update(db, audio)


def list_audio(
    db: Session, *, meeting_id: str, user_id: str, page: int, page_size: int
) -> tuple[list[MeetingAudio], int]:
    meeting_service.get_owned_meeting(db, meeting_id, user_id)
    return paginate_by(
        audio_repository.list_by_meeting,
        audio_repository.count_by_meeting,
        db,
        meeting_id,
        page=page,
        page_size=page_size,
    )


def get_owned_audio(db: Session, audio_id: str, user_id: str) -> MeetingAudio:
    audio = audio_repository.get_owned(db, audio_id, user_id)
    if audio is None:
        raise resource_not_found("音频")
    return audio


def file_size_of(audio: MeetingAudio) -> int | None:
    """原始文件大小（stat 计算，非数据库列）；文件丢失返回 None。"""
    return storage.stat_size(get_settings().storage_dir, audio.storage_key)


def read_audio_file(audio: MeetingAudio) -> bytes:
    """读取原始音频内容（下载接口用）；文件已丢失时抛 404。"""
    try:
        return storage.read_bytes(get_settings().storage_dir, audio.storage_key)
    except OSError:
        raise AppError(
            "RESOURCE_NOT_FOUND",
            "音频文件已丢失，请重新上传",
            http_status=404,
        ) from None


def retry_transcription(
    db: Session, audio_id: str, user_id: str, *, defer_processing: bool = False
) -> MeetingAudio:
    """重新转写音频；`defer_processing=True` 时只做校验，处理交由后台任务。"""
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
    if audio.type in DOCUMENT_EXTENSIONS:
        # 文稿无需 ASR：重新解析原文件并刷新转写结果
        text = _parse_document_text(content, audio.file_name)
        audio.transcript = text
        audio.status = _STATUS_TRANSCRIBED
        audio.error = None
        _resplit_segments(audio, text)
        db.commit()
        db.refresh(audio)
        return audio
    if not defer_processing:
        _ensure_duration_within_limit(content, audio.file_name)
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
            details={"reason": "audio_confirmed"},
        )
    meeting_service.get_mutable_meeting(db, audio.meeting_id, user_id)
    settings = get_settings()
    storage.delete_object(settings.storage_dir, audio.storage_key)
    for seg in audio.segments or []:
        storage.delete_object(settings.storage_dir, _chunk_key(audio_id, seg["seq"], audio.type))
    audio_repository.delete(db, audio)
