"""模型 HTTP 响应 → 统一 `AppError` 的错误细分（`ai-design.md 3.7`）。

`http_client.http_error` 委托到本模块。在状态码映射之外，进一步解析服务商
错误体（OpenAI 兼容 `{"error": {"code", "message"}}` 或 `{"code", "message"}`），
把「输入超长」与「模型不存在」从笼统的 400 里分离出来：

- 上下文超限（413 或 body 提示 context length / too many tokens 等）
  → `MODEL_INPUT_TOO_LONG`（413，不可重试；降级链可换更大上下文的模型）；
- 模型名无效（body 提示 model not found 等）
  → `MODEL_CONFIG_INVALID`（400，`details.reason="model_not_found"`）；
- 其余沿用既有映射：429 → `RATE_LIMITED`、5xx → `INTERNAL_ERROR`、
  401/403 → `MODEL_CONFIG_INVALID`、402/额度提示 → `MODEL_QUOTA_EXCEEDED`。

只记录错误码与原因，不透出服务商原始报文给前端（日志红线同 `ai-design.md 3.3`）。
"""

from __future__ import annotations

import httpx

from app.core.exceptions import AppError

QUOTA_HINTS = ("quota", "balance", "insufficient", "billing", "免费额度", "额度", "余额")

# 输入超限：状态码或错误体 code/message 命中其一即判定
INPUT_TOO_LONG_HINTS = (
    "context_length",
    "context length",
    "maximum context",
    "context window",
    "too many tokens",
    "input is too long",
    "input too long",
    "prompt is too long",
    "token limit",
    "输入过长",
    "上下文长度",
    "上下文超限",
    "超过最大",
    "token 数",
)

# 模型名无效（配置可修，非请求内容问题）
MODEL_NOT_FOUND_HINTS = (
    "model_not_found",
    "model not found",
    "model_not_found_error",
    "does not exist",
    "unknown model",
    "invalid model",
    "模型不存在",
    "模型未找到",
)

_MAX_BODY_SCAN_CHARS = 8192


def _body_text(response: httpx.Response) -> str:
    """取响应体文本（截断扫描上限）；不可读时返回空串。"""
    try:
        return (response.text or "")[:_MAX_BODY_SCAN_CHARS].lower()
    except Exception:  # noqa: BLE001 — 流未读体等场景直接放弃解析
        return ""


def _provider_error_code(response: httpx.Response) -> str:
    """提取错误体里的 `code`（`error.code` 或顶层 `code`），无则空串。"""
    try:
        data = response.json()
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    error = data.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return error["code"].lower()
    if isinstance(error, str):
        return error.lower()
    if isinstance(data.get("code"), str):
        return data["code"].lower()
    return ""


def is_quota_error(response: httpx.Response) -> bool:
    code = _provider_error_code(response)
    if "quota" in code or "billing" in code:
        return True
    text = _body_text(response)
    return any(hint in text for hint in QUOTA_HINTS)


def is_input_too_long(response: httpx.Response) -> bool:
    if response.status_code == httpx.codes.REQUEST_ENTITY_TOO_LARGE:
        return True
    code = _provider_error_code(response)
    if any(hint in code for hint in INPUT_TOO_LONG_HINTS):
        return True
    text = _body_text(response)
    return any(hint in text for hint in INPUT_TOO_LONG_HINTS)


def is_model_not_found(response: httpx.Response) -> bool:
    code = _provider_error_code(response)
    if any(hint in code for hint in MODEL_NOT_FOUND_HINTS):
        return True
    text = _body_text(response)
    return any(hint in text for hint in MODEL_NOT_FOUND_HINTS)


def input_too_long_error(service_label: str) -> AppError:
    return AppError(
        "MODEL_INPUT_TOO_LONG",
        f"{service_label}输入内容过长，超出模型上下文限制",
        http_status=413,
        retryable=False,
        details={"reason": "context_length"},
    )


def classify_error(response: httpx.Response, *, service_label: str) -> AppError:
    """把非 200 响应映射为统一 `AppError`（错误码见 `docs/api.md` 一.3）。"""
    status_code = response.status_code

    if status_code == httpx.codes.TOO_MANY_REQUESTS:
        details: dict[str, object] | None = None
        retry_after = _parse_retry_after(response)
        if retry_after is not None:
            details = {"retry_after_s": round(retry_after, 1)}
        return AppError(
            "RATE_LIMITED",
            f"{service_label}限流",
            http_status=429,
            retryable=True,
            details=details,
        )
    if 500 <= status_code < 600:
        return AppError(
            "INTERNAL_ERROR",
            f"{service_label}暂时不可用",
            http_status=500,
            retryable=True,
        )
    if status_code in (401, 403):
        return AppError(
            "MODEL_CONFIG_INVALID",
            f"{service_label}密钥无效或已失效",
            http_status=400,
            retryable=False,
        )
    # 输入超限先于额度/通用 400 判定：语义更具体，且 413 是独立错误码
    if is_input_too_long(response):
        return input_too_long_error(service_label)
    if status_code == httpx.codes.PAYMENT_REQUIRED or is_quota_error(response):
        return AppError(
            "MODEL_QUOTA_EXCEEDED",
            f"{service_label}额度不足",
            http_status=402,
            retryable=False,
        )
    if is_model_not_found(response):
        return AppError(
            "MODEL_CONFIG_INVALID",
            f"{service_label}模型名无效或不存在",
            http_status=400,
            retryable=False,
            details={"reason": "model_not_found"},
        )
    return AppError(
        "MODEL_CONFIG_INVALID",
        f"{service_label}调用失败，请检查配置",
        http_status=400,
        retryable=False,
    )


def _parse_retry_after(response: httpx.Response) -> float | None:
    # 局部导入避免与 http_client 形成环形依赖
    from app.ai.retry import parse_retry_after

    return parse_retry_after(response.headers.get("retry-after"))
