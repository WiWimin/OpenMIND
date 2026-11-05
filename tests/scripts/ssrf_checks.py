"""SSRF URL 校验（配置级，ALLOW_PRIVATE_MODEL_ENDPOINTS=false）。

运行：docker compose -f tests/compose.test.yml run --rm \
        -e ALLOW_PRIVATE_MODEL_ENDPOINTS=false -e PYTHONPATH=/app \
        backend-test python /tests/scripts/ssrf_checks.py
"""
from __future__ import annotations

from app.core.exceptions import AppError
from app.core.url_validation import validate_api_base

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))


def expect_blocked(url: str) -> None:
    try:
        validate_api_base(url, field="LLM", allow_private=False)
        check(f"拦截 {url}", False, "未拦截")
    except AppError as exc:
        check(f"拦截 {url}", exc.error_code == "MODEL_CONFIG_INVALID", exc.error_code)


def main() -> int:
    expect_blocked("http://127.0.0.1:9000/v1")
    expect_blocked("http://localhost:9000/v1")
    expect_blocked("http://169.254.169.254/latest")
    expect_blocked("http://10.0.0.5/v1")
    expect_blocked("ftp://example.com/v1")

    # 公网 HTTPS 应放行（若容器内 DNS 不可用会失败，记录真实原因）
    try:
        out = validate_api_base("https://api.openai.com/v1", field="LLM", allow_private=False)
        check("放行公网 HTTPS", out == "https://api.openai.com/v1", out)
    except AppError as exc:
        check("放行公网 HTTPS", False, exc.message)

    failed = [x for x in RESULTS if not x[1]]
    print(f"\nSUMMARY total={len(RESULTS)} passed={len(RESULTS)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
