from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AppError


class ParseError(AppError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(error_code="FILE_PARSE_FAILED", message=message, retryable=False)


@dataclass(frozen=True)
class ParsedDocument:
    file_name: str
    content: str
    parser: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_result(self, material_id: str, status: str = "processed") -> dict[str, Any]:
        return {
            "material_id": material_id,
            "status": status,
            "file_name": self.file_name,
            "content": self.content,
            "metadata": {"parser": self.parser, **self.metadata},
        }


class BaseParser(ABC):
    parser_name: str

    @abstractmethod
    def parse(self, data: bytes, file_name: str) -> ParsedDocument:
        ...
