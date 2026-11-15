"""词面相关性预筛：记录未入向量库时的廉价相关性判定。"""

from __future__ import annotations

from app.ai.rag.relevance import (
    RECORD_MIN_SCORE,
    char_overlap,
    is_lexically_relevant,
)

RECORD = "项目排期：周三完成设计稿，周五联调，下周三上线。"


def test_related_question_scores_above_threshold() -> None:
    score = char_overlap("项目排期是什么时候", RECORD)
    assert score >= RECORD_MIN_SCORE
    assert is_lexically_relevant("项目排期是什么时候", RECORD)


def test_unrelated_question_scores_below_threshold() -> None:
    score = char_overlap("公司的年度市场预算是多少", RECORD)
    assert score < RECORD_MIN_SCORE
    assert not is_lexically_relevant("公司的年度市场预算是多少", RECORD)


def test_empty_or_short_query_skips_filtering() -> None:
    """bigram 不足的问句（「结论？」/ 空问句）不做词面过滤，避免误判为无证据。"""
    assert char_overlap("结论", RECORD) == 1.0
    assert char_overlap("", RECORD) == 1.0


def test_empty_text_scores_zero() -> None:
    assert char_overlap("项目排期是什么时候", "") == 0.0
