"""M00-08 模型连通性验证：分别探测 LLM 与 Embedding API。

用法（仓库根目录或 backend 目录均可）：
    python backend/scripts/check_ai.py
    python backend/scripts/check_ai.py --only llm --timeout 30
    docker compose -f docker/compose.dev.yml exec backend python scripts/check_ai.py

退出码：0 全部通过；1 存在失败；2 配置缺失或仍为占位值。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_CONFIG = 2

PLACEHOLDER_VALUES = {"", "change-me", "changeme", "your-key-here"}


def find_env_file(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docker" / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_env(env_file: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file:
        text = env_file.read_text(encoding="utf-8-sig")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            values[key.strip().lstrip("\ufeff")] = value.strip().strip("'\"")
    for key, value in os.environ.items():
        if key.startswith(("LLM_", "EMBEDDING_")):
            values[key] = value
    return values


def config_issues(values: dict[str, str], prefix: str) -> list[str]:
    issues: list[str] = []
    base = values.get(f"{prefix}_API_BASE", "").strip()
    key = values.get(f"{prefix}_API_KEY", "").strip()
    model = values.get(f"{prefix}_MODEL", "").strip()
    if not base:
        issues.append(f"{prefix}_API_BASE 未设置")
    elif "example.com" in base.lower():
        issues.append(f"{prefix}_API_BASE 仍是占位值（{base}）")
    if key.lower() in PLACEHOLDER_VALUES:
        issues.append(f"{prefix}_API_KEY 未填写真实密钥")
    if not model:
        issues.append(f"{prefix}_MODEL 未设置")
    return issues


def endpoint(base: str, path: str) -> str:
    return base.rstrip("/") + path


def describe_error(exc: Exception, prefix: str) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f"MODEL_TIMEOUT：{prefix} 请求超时，请检查网络或增大 --timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return f"AUTH：密钥无效或无权限（HTTP {status}）"
        if status == 404:
            return "ENDPOINT：路径不存在，请检查 API_BASE 是否需要 /v1 后缀"
        if status == 429:
            return f"RATE_LIMITED：触发限流（HTTP {status}）"
        body = exc.response.text.strip().replace("\n", " ")[:200]
        return f"HTTP {status}：{body}"
    if isinstance(exc, httpx.ConnectError):
        return f"NETWORK：无法连接（{exc}）"
    return f"{type(exc).__name__}：{exc}"


def check_llm(values: dict[str, str], timeout: float) -> tuple[bool, str, bool]:
    issues = config_issues(values, "LLM")
    if issues:
        return False, "；".join(issues), True

    base = values["LLM_API_BASE"]
    model = values["LLM_MODEL"]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复两个字：正常"}],
        "max_tokens": 64,
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {values['LLM_API_KEY']}",
        "Content-Type": "application/json",
    }
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            url = endpoint(base, "/chat/completions")
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return False, describe_error(exc, "LLM"), False
    elapsed_ms = (time.perf_counter() - started) * 1000

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return False, "MODEL_OUTPUT_INVALID：响应中缺少 choices[0].message.content", False

    text = (content or "").strip().replace("\n", " ")[:80]
    usage = data.get("usage", {})
    tokens = usage.get("total_tokens", "?")
    return True, f"model={model} 耗时={elapsed_ms:.0f}ms tokens={tokens} 回复={text}", False


def check_embedding(values: dict[str, str], timeout: float) -> tuple[bool, str, bool]:
    issues = config_issues(values, "EMBEDDING")
    if issues:
        return False, "；".join(issues), True

    base = values["EMBEDDING_API_BASE"]
    model = values["EMBEDDING_MODEL"]
    payload = {"model": model, "input": ["OpenMIND 连通性测试：会议资料检索"]}
    headers = {
        "Authorization": f"Bearer {values['EMBEDDING_API_KEY']}",
        "Content-Type": "application/json",
    }
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint(base, "/embeddings"), json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return False, describe_error(exc, "Embedding"), False
    elapsed_ms = (time.perf_counter() - started) * 1000

    try:
        vector = data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError):
        return False, "MODEL_OUTPUT_INVALID：响应中缺少 data[0].embedding", False

    dims = len(vector)
    expected_raw = values.get("EMBEDDING_DIM", "").strip()
    note = ""
    if expected_raw.isdigit():
        expected = int(expected_raw)
        if expected != dims:
            note = f"（警告：EMBEDDING_DIM={expected} 与实际不一致，向量表建表前必须统一）"
    return True, f"model={model} 维度={dims} 耗时={elapsed_ms:.0f}ms {note}".rstrip(), False


def run_check(name: str, func, values: dict[str, str], timeout: float) -> tuple[bool, bool]:
    print(f"== {name} ==")
    ok, message, config_only = func(values, timeout)
    marker = "[OK]  " if ok else "[FAIL]"
    print(f"{marker} {message}")
    print()
    return ok, config_only


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 LLM 与 Embedding API 连通性")
    parser.add_argument("--only", choices=["llm", "embedding"], help="只检查其中一项")
    parser.add_argument("--timeout", type=float, default=30.0, help="单次请求超时秒数，默认 30")
    parser.add_argument("--env-file", help="指定环境变量文件，默认自动查找仓库 docker/.env")
    args = parser.parse_args()

    env_file = find_env_file(args.env_file)
    values = load_env(env_file)
    source = str(env_file) if env_file else "仅进程环境变量（未找到 docker/.env）"
    print(f"配置来源：{source}")
    print(f"LLM_API_BASE={values.get('LLM_API_BASE', '(未设置)')}  "
          f"LLM_MODEL={values.get('LLM_MODEL', '(未设置)')}")
    print(f"EMBEDDING_API_BASE={values.get('EMBEDDING_API_BASE', '(未设置)')}  "
          f"EMBEDDING_MODEL={values.get('EMBEDDING_MODEL', '(未设置)')}  "
          f"EMBEDDING_DIM={values.get('EMBEDDING_DIM', '(未设置)')}")
    print("密钥仅在服务端使用，本脚本不打印密钥内容。")
    print()

    outcomes: list[tuple[bool, bool]] = []
    if args.only != "embedding":
        outcomes.append(run_check("1/2 LLM 文本生成", check_llm, values, args.timeout))
    if args.only != "llm":
        outcomes.append(run_check("2/2 Embedding 向量生成", check_embedding, values, args.timeout))

    failed = [outcome for outcome in outcomes if not outcome[0]]
    if failed:
        if all(config_only for _, config_only in failed):
            print("结论：配置缺失或仍为占位值，请填写 docker/.env 后重试。")
            return EXIT_CONFIG
        print("结论：存在真实调用失败，请按上方错误码排查。")
        return EXIT_FAIL
    print("全部通过：M00-08 模型与向量 API 连通性验证成功。")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
