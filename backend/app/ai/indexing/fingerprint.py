"""索引参数指纹：标识存量分块由哪套参数/模型产出。

增量索引复用分块前必须校验指纹一致：换 Embedding 模型、维度、分块参数
都会使旧向量失效（同维不同模型同样不可比），指纹不匹配即重新解析/向量化。

指纹不含用户与文件内容，仅描述「索引环境」，因此可跨记录比对。
"""

from __future__ import annotations

import hashlib

from app.core.config import Settings


def build_index_fingerprint(settings: Settings) -> str:
    """按当前索引环境计算指纹（sha256 hex）。

    `rag_index_fingerprint_version` 递增可使全部存量分块失效重建，
    用于分块算法本身变更（如切分规则调整）的场景。
    """
    raw = "|".join(
        [
            settings.embedding_model or "",
            str(settings.embedding_dim),
            str(settings.rag_chunk_size),
            str(settings.rag_chunk_overlap),
            f"chunker_v{settings.rag_index_fingerprint_version}",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_sha256(content: bytes) -> str:
    """文件内容摘要（sha256 hex，64 位）：增量索引的同内容判定依据。"""
    return hashlib.sha256(content).hexdigest()
