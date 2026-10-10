from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.parsers import SUPPORTED_EXTENSIONS, ParseError, ParserService, parse_bytes


def test_supported_extensions() -> None:
    assert SUPPORTED_EXTENSIONS == (".pdf", ".docx", ".txt")
    assert ParserService.supported_extensions() == (".pdf", ".docx", ".txt")


@pytest.mark.parametrize("suffix", [".txt", ".TXT", ".Txt"])
def test_dispatch_is_case_insensitive(suffix: str) -> None:
    result = parse_bytes(b"content here", f"report{suffix}")
    assert result.parser == "txt"
    assert result.content == "content here"


def test_unsupported_extension_reports_reason() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_bytes(b"data", "photo.png")
    assert excinfo.value.reason == "unsupported_format"
    assert ".png" in excinfo.value.message


def test_extension_without_suffix_reports_reason() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_bytes(b"data", "README")
    assert excinfo.value.reason == "unsupported_format"


def test_empty_bytes_reports_reason() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_bytes(b"", "empty.txt")
    assert excinfo.value.reason == "empty_content"


def test_file_name_is_normalized_to_basename() -> None:
    result = parse_bytes(b"payload", "../../etc/secret.txt")
    assert result.file_name == "secret.txt"


def test_parse_file_reads_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "meeting-notes.txt"
    path.write_text("standup notes", encoding="utf-8")
    result = ParserService().parse_file(path)
    assert result.file_name == "meeting-notes.txt"
    assert result.content == "standup notes"


def test_parse_file_missing_reports_invalid_file(tmp_path: Path) -> None:
    with pytest.raises(ParseError) as excinfo:
        ParserService().parse_file(tmp_path / "ghost.txt")
    assert excinfo.value.reason == "invalid_file"


def test_parse_error_carries_unified_error_code() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_bytes(b"data", "video.mp4")
    assert excinfo.value.error_code == "FILE_PARSE_FAILED"
    assert excinfo.value.retryable is False
