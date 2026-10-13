from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.embeddings import EmbeddingClient  # noqa: E402
from app.ai.llm import LLMClient  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_CONFIG = 2

_PLACEHOLDERS = {"", "change-me", "changeme", "your-key-here"}


def config_missing(prefix: str) -> list[str]:
    settings = get_settings()
    issues: list[str] = []
    base = getattr(settings, f"{prefix}_api_base", "").strip()
    key = getattr(settings, f"{prefix}_api_key", "").strip()
    model = getattr(settings, f"{prefix}_model", "").strip()
    if not base or "example.com" in base.lower():
        issues.append(f"{prefix}_API_BASE 未配置或仍为占位值")
    if key.lower() in _PLACEHOLDERS:
        issues.append(f"{prefix}_API_KEY 未填写真实密钥")
    if not model:
        issues.append(f"{prefix}_MODEL 未设置")
    return issues


def check_llm(timeout_s: float) -> tuple[bool, str, bool]:
    issues = config_missing("llm")
    if issues:
        return False, "；".join(issues), True
    try:
        result = LLMClient().chat(
            [{"role": "user", "content": "请只回复两个字：正常"}],
            max_tokens=512,
            temperature=0,
            timeout_s=timeout_s,
        )
    except AppError as exc:
        return False, f"{exc.error_code}：{exc.message}", False
    text = result.text.strip().replace("\n", " ")[:80]
    message = f"model={result.model} 耗时={result.latency_ms}ms tokens={result.usage} 回复={text}"
    return True, message, False


def check_embedding() -> tuple[bool, str, bool]:
    issues = config_missing("embedding")
    if issues:
        return False, "；".join(issues), True
    client = EmbeddingClient()
    try:
        vectors = client.embed(["OpenMIND 连通性测试：会议资料检索"])
    except AppError as exc:
        return False, f"{exc.error_code}：{exc.message}", False
    return True, f"model={client.model} 维度={len(vectors[0])} 条数={len(vectors)}", False


def run_check(name: str, func, *args) -> tuple[bool, bool]:
    print(f"== {name} ==")
    ok, message, config_only = func(*args)
    print(f"{'[OK]  ' if ok else '[FAIL]'} {message}")
    print()
    return ok, config_only


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 LLM 与 Embedding API 连通性")
    parser.add_argument("--only", choices=["llm", "embedding"], help="只检查其中一项")
    parser.add_argument("--timeout", type=float, default=30.0, help="LLM 单次请求超时秒数，默认 30")
    args = parser.parse_args()

    settings = get_settings()
    llm_line = (
        f"LLM_API_BASE={settings.llm_api_base or '(未设置)'}  "
        f"LLM_MODEL={settings.llm_model or '(未设置)'}"
    )
    print(llm_line)
    print(
        "EMBEDDING_API_BASE="
        f"{settings.embedding_api_base or '(未设置)'}  "
        f"EMBEDDING_MODEL={settings.embedding_model or '(未设置)'}  "
        f"EMBEDDING_DIM={settings.embedding_dim}"
    )
    print("密钥仅在服务端使用，本脚本不打印密钥内容。")
    print()

    outcomes: list[tuple[bool, bool]] = []
    if args.only != "embedding":
        outcomes.append(run_check("1/2 LLM 文本生成", check_llm, args.timeout))
    if args.only != "llm":
        outcomes.append(run_check("2/2 Embedding 向量生成", check_embedding))

    failed = [outcome for outcome in outcomes if not outcome[0]]
    if failed:
        if all(config_only for _, config_only in failed):
            print("结论：配置缺失或仍为占位值，请填写 docker/.env 后重试。")
            return EXIT_CONFIG
        print("结论：存在真实调用失败，请按上方错误码排查。")
        return EXIT_FAIL
    print("全部通过：模型与向量 API 连通性验证成功。")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
