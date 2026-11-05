"""cn.bing.com 网页检索（免 key）。

本环境实测：DuckDuckGo 全端点被墙、智谱 web_search 工具不执行，
cn.bing.com 0.8s 可达且中文结果质量好，故为默认源。
页面结构属外部契约：解析容错，改版导致解析不出时由上层降级为拒答。
"""

from __future__ import annotations

import html as html_lib
import re

import httpx

from app.ai.websearch import WebResult

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 自然结果条目：b_algo 不会嵌套，非贪婪截取即可
_ITEM_RE = re.compile(r'<li class="b_algo".*?</li>', re.S)
_HREF_RE = re.compile(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_SNIPPET_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip(fragment: str) -> str:
    return html_lib.unescape(_TAG_RE.sub("", fragment)).strip()


def parse_results(page: str, max_results: int) -> list[WebResult]:
    """从 Bing 结果页 HTML 提取 (title, url, snippet)；解析失败返回空列表。"""
    results: list[WebResult] = []
    for item in _ITEM_RE.findall(page):
        href = _HREF_RE.search(item)
        if not href:
            continue
        url = html_lib.unescape(href.group(1)).strip()
        title = _strip(href.group(2))
        if not url.startswith(("http://", "https://")) or not title:
            continue
        snippet_match = _SNIPPET_RE.search(item)
        snippet = _strip(snippet_match.group(1)) if snippet_match else ""
        results.append(WebResult(title=title, url=url, snippet=snippet[:500]))
        if len(results) >= max_results:
            break
    return results


def search(query: str, *, max_results: int = 5, timeout_s: float = 10.0) -> list[WebResult]:
    response = httpx.get(
        "https://cn.bing.com/search",
        params={"q": query, "setlang": "zh-hans", "count": str(max_results)},
        headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=timeout_s,
        follow_redirects=True,
    )
    response.raise_for_status()
    return parse_results(response.text, max_results)
