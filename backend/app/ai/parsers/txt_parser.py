from __future__ import annotations

from app.ai.parsers.base import BaseParser, ParsedDocument, ParseError

_UTF8_BOM = b"\xef\xbb\xbf"


class TxtParser(BaseParser):
    parser_name = "txt"

    def parse(self, data: bytes, file_name: str) -> ParsedDocument:
        if b"\x00" in data:
            raise ParseError("invalid_file", f"文本文件包含二进制数据，无法解析：{file_name}")
        encoding = _decode(data)
        if encoding is None:
            raise ParseError("invalid_file", f"文本文件编码无法识别：{file_name}")
        text = data.decode(encoding, errors="replace").replace("\r\n", "\n").replace("\r", "\n")

        content = text.strip()
        if not content:
            raise ParseError("empty_content", f"文本文件内容为空：{file_name}")

        return ParsedDocument(
            file_name=file_name,
            content=content,
            parser=self.parser_name,
            metadata={
                "encoding": encoding,
                "char_count": len(content),
            },
        )


def _decode(data: bytes) -> str | None:
    if data.startswith(_UTF8_BOM):
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
        return "utf-8-sig"
    for encoding in ("utf-8", "gb18030"):
        try:
            data.decode(encoding)
        except UnicodeDecodeError:
            continue
        return encoding
    return None
