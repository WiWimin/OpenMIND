from __future__ import annotations

from io import BytesIO

from pypdf import PasswordType, PdfReader

from app.ai.parsers.base import BaseParser, ParsedDocument, ParseError


class PdfParser(BaseParser):
    parser_name = "pdf"

    def parse(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            reader = PdfReader(BytesIO(data))
        except Exception as exc:
            raise ParseError("invalid_file", f"PDF 文件无法读取或已损坏：{file_name}") from exc

        if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
            raise ParseError(
                "encrypted_pdf", f"PDF 已加密，无法读取，请上传未加密的文件：{file_name}"
            )

        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")

        content = "\n".join(part.strip() for part in pages if part.strip())
        if not content:
            raise ParseError(
                "no_text_layer",
                (
                    f"PDF 未提取到文本（可能是扫描件，暂不支持 OCR，"
                    f"请上传可提取文本的文件）：{file_name}"
                ),
            )

        return ParsedDocument(
            file_name=file_name,
            content=content,
            parser=self.parser_name,
            metadata={
                "page_count": len(reader.pages),
                "char_count": len(content),
            },
        )
