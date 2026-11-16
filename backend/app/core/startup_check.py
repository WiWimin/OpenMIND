"""启动时数据库迁移版本核对：只告警，不阻断启动。

背景：代码新增列/表而数据库未执行 `alembic upgrade head` 时，接口会以未捕获
的 500 失败；由于这类 500 由最外层 `ServerErrorMiddleware` 生成、不携带 CORS
头，浏览器只能看到「Network Error」，排查成本高。启动时比对 `alembic_version`
与代码 head，不一致直接在日志里给出可执行的修复命令。

测试环境用 `Base.metadata.create_all` 建表、没有 `alembic_version`，读取失败时
静默跳过。
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

_MIGRATION_HINT = "请执行：alembic upgrade head（backend/ 下）"


def log_migration_status() -> None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        backend_dir = Path(__file__).resolve().parents[2]
        config = Config()
        config.set_main_option("script_location", str(backend_dir / "alembic"))
        head = ScriptDirectory.from_config(config).get_current_head()
        with engine.connect() as connection:
            current = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
    except Exception:  # noqa: BLE001 — 无 alembic_version（测试库）或 alembic 不可用
        return

    if current is None:
        logger.error("数据库未初始化迁移版本，代码 head=%s。%s", head, _MIGRATION_HINT)
    elif current != head:
        logger.error(
            "数据库迁移版本落后：当前=%s head=%s。%s", current, head, _MIGRATION_HINT
        )
    else:
        logger.info("数据库迁移版本已对齐：%s", head)
