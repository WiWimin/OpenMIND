from __future__ import annotations

import pytest

from app.ai.indexing import split_text


def test_empty_text_returns_empty() -> None:
    assert split_text("") == []
    assert split_text("   \n  ") == []


def test_short_text_returns_single_chunk() -> None:
    text = "短文本"
    assert split_text(text, chunk_size=800) == [text]


def test_invalid_overlap_raises() -> None:
    with pytest.raises(ValueError):
        split_text("abc", chunk_size=10, overlap=10)


def test_long_text_preserves_content() -> None:
    text = "abcdefghijklmnopqrstuvwxyz0123456789"
    chunks = split_text(text, chunk_size=10, overlap=2)
    assert chunks
    reconstructed = chunks[0] + "".join(chunk[2:] for chunk in chunks[1:])
    assert reconstructed == text


def test_consecutive_chunks_overlap() -> None:
    text = "abcdefghijkl"
    chunks = split_text(text, chunk_size=6, overlap=2)
    assert len(chunks) == 2
    assert chunks[1][:2] == chunks[0][-2:]


def test_chunks_do_not_exceed_limit() -> None:
    text = "。".join(f"第{i}段会议内容，讨论了若干议题与结论。" for i in range(100))
    chunks = split_text(text, chunk_size=800, overlap=120)
    assert len(chunks) > 1
    for chunk in chunks:
        assert 0 < len(chunk) <= 800 + 120


def test_splits_at_sentence_boundary() -> None:
    text = "第一句。第二句！第三句？第四句。"
    chunks = split_text(text, chunk_size=6, overlap=1)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk
