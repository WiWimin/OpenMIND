"""DuckDuckGo 检索（ddgs，免 key）。

仅在可达网络下可用（本机实测被墙时会超时，由上层降级）；
`WEB_SEARCH_PROVIDER=ddg` 时启用。
"""

from __future__ import annotations

from app.ai.websearch import WebResult


def search(query: str, *, max_results: int = 5, timeout_s: float = 10.0) -> list[WebResult]:
    from ddgs import DDGS

    ddgs = DDGS(timeout=timeout_s)
    rows = ddgs.text(query, max_results=max_results) or []
    results: list[WebResult] = []
    for row in rows:
        url = str(row.get("href") or row.get("URL") or "").strip()
        title = str(row.get("title") or "").strip()
        if not url or not title:
            continue
        results.append(
            WebResult(title=title, url=url, snippet=str(row.get("body") or "")[:500])
        )
    return results
