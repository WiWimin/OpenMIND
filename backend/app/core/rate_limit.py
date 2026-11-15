from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from jwt.exceptions import PyJWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, error_body
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_S = 60.0

# AI 生成类路径（按用户计数，避免误伤普通页面访问）
_AI_PATH_MARKERS = (
    "/chat",
    "/organize",
    "/minutes/generate",
    "/prepare",
    "/action-items/extract",
    "/issues/extract",
    "/meeting-templates/generate",
)
# ASR 触发类接口（POST 才计数）：上传、实时分片、分片重试、整体重试。
# 单独成组是因为分片间隔短（约 5s/片），套用 LLM 的 20/min 会误杀实时录音。
_ASR_PATH_MARKER = "/audio"
# 进程内限流豁免：探针与文档
_SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class SlidingWindowLimiter:
    """进程内滑动窗口限流器（线程安全，多 worker / 多实例不共享）。"""

    def __init__(self, *, max_keys: int = 10000, window_s: float = _DEFAULT_WINDOW_S) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = {}
        self._max_keys = max_keys
        self._window_s = window_s

    def hit(self, key: str, limit: int, window_s: float | None = None) -> float | None:
        """记录一次调用。未超限返回 None；超限返回需等待秒数（≥1），且本次不计入。"""
        window = self._window_s if window_s is None else window_s
        now = time.monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self._max_keys:
                    self._evict(now, window)
                events = deque()
                self._events[key] = events
            cutoff = now - window
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(events[0] + window - now, 1.0)
            events.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _evict(self, now: float, window: float) -> None:
        """键空间超限时淘汰已过期的键；仍超限则淘汰最早触发的键。"""
        for key in list(self._events):
            events = self._events[key]
            if not events or events[-1] + window <= now:
                del self._events[key]
        if len(self._events) >= self._max_keys and self._events:
            oldest = min(self._events, key=lambda k: self._events[k][0])
            del self._events[oldest]


_limiter = SlidingWindowLimiter()


def get_limiter() -> SlidingWindowLimiter:
    return _limiter


def client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def token_subject(request: Request) -> str | None:
    """从 Authorization 头解析 JWT sub（不查库，仅用于计数分组）。"""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        payload = decode_access_token(header.split(" ", 1)[1])
    except PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def _raise_limited(retry_after: float, group: str) -> None:
    raise AppError(
        "RATE_LIMITED",
        "操作过于频繁，请稍后再试",
        http_status=429,
        retryable=True,
        details={"retry_after": round(retry_after, 1), "group": group},
    )


def enforce_login_rate_limit(request: Request, username: str) -> None:
    """登录防爆破：按「IP + 用户名」计数，超限抛 429 RATE_LIMITED。"""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    key = f"login:{client_ip(request)}:{username.strip().lower()}"
    retry_after = _limiter.hit(key, settings.rate_limit_login_per_minute)
    if retry_after is not None:
        _raise_limited(retry_after, "login")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """全局接口限流：登录组按 IP，AI/ASR 组按用户，其余默认按用户（回退 IP）。"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        if settings.rate_limit_enabled and not self._skipped(path):
            retry_after, group = self._check(request, path, settings)
            if retry_after is not None:
                return JSONResponse(
                    status_code=429,
                    content=error_body(
                        "RATE_LIMITED",
                        "操作过于频繁，请稍后再试",
                        retryable=True,
                        details={"retry_after": round(retry_after, 1), "group": group},
                    ),
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )
        return await call_next(request)

    @staticmethod
    def _skipped(path: str) -> bool:
        return path in _SKIP_PATHS or path.endswith("/health/db")

    @staticmethod
    def _check(
        request: Request, path: str, settings: Settings
    ) -> tuple[float | None, str]:
        if path.endswith("/auth/login") or path.endswith("/auth/register"):
            key = f"ip:{client_ip(request)}"
            limit = settings.rate_limit_login_per_minute
            group = "login"
        elif any(marker in path for marker in _AI_PATH_MARKERS):
            group = "ai"
            limit = settings.rate_limit_ai_per_minute
            sub = token_subject(request)
            key = f"user:{sub}" if sub else f"ip:{client_ip(request)}"
        elif request.method == "POST" and _ASR_PATH_MARKER in path:
            group = "asr"
            limit = settings.rate_limit_asr_per_minute
            sub = token_subject(request)
            key = f"user:{sub}" if sub else f"ip:{client_ip(request)}"
        else:
            group = "default"
            limit = settings.rate_limit_default_per_minute
            sub = token_subject(request)
            key = f"user:{sub}" if sub else f"ip:{client_ip(request)}"
        return _limiter.hit(key, limit), group
