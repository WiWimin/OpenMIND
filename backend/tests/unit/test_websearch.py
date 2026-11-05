"""联网检索：Bing 结果解析、provider 分发与降级。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.websearch import WebResult, bing, web_search

_PAGE = """
<html><body>
<li class="b_algo"><div><h2><a href="https://example.com/one?x=1&amp;y=2">标题一 &amp; 详情</a></h2>
<p>片段<strong>加粗</strong>文本</p></div></li>
<li class="b_algo"><div><h2><a href="https://example.com/two">标题二</a></h2></div></li>
<li class="other"><h2><a href="https://skip.com">不应出现</a></h2></li>
</body></html>
"""


def test_bing_parse_results_extracts_and_strips() -> None:
    results = bing.parse_results(_PAGE, max_results=5)

    assert len(results) == 2
    assert results[0].title == "标题一 & 详情"
    assert results[0].url == "https://example.com/one?x=1&y=2"
    assert results[0].snippet == "片段加粗文本"
    assert results[1].url == "https://example.com/two"
    assert results[1].snippet == ""


def test_bing_parse_results_caps_at_max_results() -> None:
    assert len(bing.parse_results(_PAGE, max_results=1)) == 1


def test_bing_parse_results_ignores_non_http_and_malformed() -> None:
    page = '<li class="b_algo"><h2><a href="/local">相对链接</a></h2></li>'
    assert bing.parse_results(page, max_results=5) == []


def test_web_search_disabled_returns_empty() -> None:
    # tests/conftest.py 固定 WEB_SEARCH_ENABLED=false
    assert web_search("任意问题") == []


def test_web_search_dispatches_bing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        web_search_enabled=True,
        web_search_provider="bing",
        web_search_max_results=3,
        web_search_timeout_s=5.0,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    seen: dict[str, object] = {}

    def fake_search(query: str, *, max_results: int, timeout_s: float) -> list[WebResult]:
        seen.update(query=query, max_results=max_results, timeout_s=timeout_s)
        return [WebResult(title="t", url="https://e.com", snippet="s")]

    monkeypatch.setattr(bing, "search", fake_search)

    results = web_search("查询词")

    assert len(results) == 1
    assert seen == {"query": "查询词", "max_results": 3, "timeout_s": 5.0}


def test_web_search_failure_degrades_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        web_search_enabled=True,
        web_search_provider="bing",
        web_search_max_results=3,
        web_search_timeout_s=5.0,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)

    def boom(*args: object, **kwargs: object) -> list[WebResult]:
        raise RuntimeError("被墙/改版/超时")

    monkeypatch.setattr(bing, "search", boom)

    assert web_search("查询词") == []


def test_web_search_unknown_provider_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        web_search_enabled=True,
        web_search_provider="unknown",
        web_search_max_results=3,
        web_search_timeout_s=5.0,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)

    assert web_search("查询词") == []
