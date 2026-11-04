"""验证 ALLOW_GLOBAL_FALLBACK 默认关闭：未配置 BYOK 的用户应得到 MODEL_CONFIG_REQUIRED。

运行：docker compose -f tests/compose.test.yml run --rm -e ALLOW_GLOBAL_FALLBACK=false \
        backend-test python /tests/scripts/fallback_default_off.py
"""
from __future__ import annotations

import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.user import User
from app.services.model_config_service import build_llm_client, resolve_model_config

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))


def main() -> int:
    settings = get_settings()
    check("ALLOW_GLOBAL_FALLBACK=false", settings.allow_global_fallback is False,
          str(settings.allow_global_fallback))

    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as db:
        uid = f"fb-{uuid.uuid4().hex[:10]}"
        db.add(User(user_id=uid, name=f"fb-{uuid.uuid4().hex[:8]}", password_hash="x"))
        db.commit()

        config = resolve_model_config(db, uid)
        check("未配置用户 LLM 为空", config.llm_api_base == "" and config.llm_model == "",
              f"base='{config.llm_api_base}' model='{config.llm_model}'")
        try:
            build_llm_client(config).chat([{"role": "user", "content": "ping"}])
            check("未配置用户调用 LLM 抛 MODEL_CONFIG_REQUIRED", False, "未抛错")
        except AppError as exc:
            check("未配置用户调用 LLM 抛 MODEL_CONFIG_REQUIRED", exc.error_code == "MODEL_CONFIG_REQUIRED",
                  f"{exc.error_code}/{exc.http_status}")

        # Embedding 为服务端统一配置，与 fallback 无关，仍可用
        check("Embedding 仍取服务端配置", bool(config.embedding_api_base and config.embedding_model),
              f"{config.embedding_api_base}/{config.embedding_model}")

    failed = [x for x in RESULTS if not x[1]]
    print(f"\nSUMMARY total={len(RESULTS)} passed={len(RESULTS)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
