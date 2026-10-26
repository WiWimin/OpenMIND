from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.exceptions import AppError

_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "host.docker.internal",
    "kubernetes.default.svc",
}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")


def _invalid(field: str, reason: str) -> AppError:
    return AppError(
        "MODEL_CONFIG_INVALID",
        f"{field} 地址不安全：{reason}",
        http_status=400,
    )


def _resolve_host(host: str, port: int) -> set[str]:
    addresses: set[str] = set()
    for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        addresses.add(info[4][0].split("%", 1)[0])
    return addresses


def validate_api_base(value: str, *, field: str, allow_private: bool = False) -> str:
    """Validate a user-supplied model API base and block common SSRF targets."""
    raw = (value or "").strip()
    if not raw:
        raise _invalid(field, "不能为空")

    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise _invalid(field, "URL 格式无效") from None

    if parsed.scheme not in {"http", "https"}:
        raise _invalid(field, "仅支持 http/https")
    if parsed.username or parsed.password:
        raise _invalid(field, "不允许在 URL 中嵌入账号或密码")
    if parsed.query or parsed.fragment:
        raise _invalid(field, "不允许携带 query 或 fragment")

    try:
        host = parsed.hostname
    except ValueError:
        raise _invalid(field, "主机名格式无效") from None
    if not host:
        raise _invalid(field, "缺少主机名")

    normalized_host = host.rstrip(".").lower()
    if allow_private:
        return raw.rstrip("/")

    if parsed.scheme != "https":
        raise _invalid(field, "非本机模型服务必须使用 https")
    if normalized_host in _BLOCKED_HOSTS or any(
        normalized_host.endswith(suffix) for suffix in _BLOCKED_SUFFIXES
    ):
        raise _invalid(field, "不允许访问本机或内部主机")

    try:
        literal_ip = ipaddress.ip_address(normalized_host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not literal_ip.is_global:
            raise _invalid(field, "不允许访问私有、回环或保留地址")
        return raw.rstrip("/")

    try:
        addresses = _resolve_host(normalized_host, port or 443)
    except OSError:
        raise _invalid(field, "主机名无法解析") from None

    if not addresses:
        raise _invalid(field, "主机名无法解析")

    for address in addresses:
        try:
            resolved = ipaddress.ip_address(address)
        except ValueError:
            raise _invalid(field, "主机解析结果无效") from None
        if not resolved.is_global:
            raise _invalid(field, "主机解析到私有、回环或保留地址")

    return raw.rstrip("/")
