from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?])\s*|\n+")


def split_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须满足 0 <= overlap < chunk_size")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]
    segments = _segment(normalized, chunk_size)
    chunks: list[str] = []
    current = ""
    for segment in segments:
        if not current:
            current = segment
            continue
        if len(current) + len(segment) + 1 <= chunk_size:
            current = f"{current}\n{segment}"
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}{segment}" if tail else segment
    if current:
        chunks.append(current)
    return chunks


def _segment(text: str, chunk_size: int) -> list[str]:
    pieces = [piece.strip() for piece in _SENTENCE_BOUNDARY.split(text) if piece.strip()]
    result: list[str] = []
    for piece in pieces:
        if len(piece) > chunk_size:
            result.extend(piece[i : i + chunk_size] for i in range(0, len(piece), chunk_size))
        else:
            result.append(piece)
    return result
