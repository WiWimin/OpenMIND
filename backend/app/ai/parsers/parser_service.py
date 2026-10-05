from __future__ import annotations

from pathlib import Path

from app.ai.parsers.base import BaseParser, ParsedDocument, ParseError
from app.ai.parsers.docx_parser import DocxParser
from app.ai.parsers.pdf_parser import PdfParser
from app.ai.parsers.txt_parser import TxtParser

_PARSERS: dict[str, type[BaseParser]] = {
    ".pdf": PdfParser,
    ".docx": DocxParser,
    ".txt": TxtParser,
}

SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(_PARSERS)


class ParserService:
    def __init__(self) -> None:
        self._parsers = {suffix: parser() for suffix, parser in _PARSERS.items()}

    @staticmethod
    def supported_extensions() -> tuple[str, ...]:
        return SUPPORTED_EXTENSIONS

    def parse_bytes(self, data: bytes, file_name: str) -> ParsedDocument:
        if not data:
            raise ParseError("empty_content", f"文件内容为空：{file_name}")

        normalized_name = Path(file_name).name
        suffix = Path(normalized_name).suffix.lower()
        parser = self._parsers.get(suffix)
        if parser is None:
            shown = suffix or normalized_name
            raise ParseError(
                "unsupported_format",
                f"不支持的文件类型：{shown}，目前仅支持 PDF、DOCX、TXT",
            )

        try:
            return parser.parse(data, normalized_name)
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError("parse_failed", f"文件解析失败：{normalized_name}") from exc

    def parse_file(self, path: Path | str) -> ParsedDocument:
        file_path = Path(path)
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            raise ParseError("invalid_file", f"文件读取失败：{file_path.name}") from exc
        return self.parse_bytes(data, file_path.name)


_default_service = ParserService()


def parse_bytes(data: bytes, file_name: str) -> ParsedDocument:
    return _default_service.parse_bytes(data, file_name)


def parse_file(path: Path | str) -> ParsedDocument:
    return _default_service.parse_file(path)
