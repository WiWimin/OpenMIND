"""全量重建向量索引。

用途：embedding 模型或维度、分块参数变更后，把已有会议材料与知识库文档重新
向量化，使存量向量与新模型处于同一向量空间（同维不同模型同样不可比），并回填
`content_hash` / `index_fingerprint` / `indexed_at`（迁移 0028）。

增量语义：
- 默认跳过「指纹已匹配且分块完整」的记录（幂等重跑零 API 消耗）；
- `--force` 忽略指纹全部重建；
- 指纹为空的存量记录视为「产出参数未知」，默认重建后才可作为增量复用源。

用法：
    python scripts/reindex_all.py --dry-run   # 只统计，不写入
    python scripts/reindex_all.py             # 增量重建并提交
    python scripts/reindex_all.py --force     # 全量重建
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.indexing import build_index_fingerprint, file_sha256  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.knowledge_document import KnowledgeDocument  # noqa: E402
from app.models.material import MeetingMaterial  # noqa: E402
from app.models.user import utc_now  # noqa: E402
from app.repositories import chunk_repository, knowledge_chunk_repository  # noqa: E402
from app.services import indexing_service, knowledge_service  # noqa: E402
from app.utils import storage  # noqa: E402


def _needs_rebuild(row: object, fingerprint: str, chunk_count: int, force: bool) -> bool:
    if force:
        return True
    if getattr(row, "index_fingerprint", None) != fingerprint:
        return True
    return chunk_count <= 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只统计待重建对象，不写入")
    parser.add_argument(
        "--force", action="store_true", help="忽略指纹匹配，全部重建"
    )
    args = parser.parse_args()

    settings = get_settings()
    fingerprint = build_index_fingerprint(settings)
    print(f"当前索引指纹 fingerprint={fingerprint[:12]}…")

    db = SessionLocal()
    try:
        materials = (
            db.query(MeetingMaterial)
            .filter(MeetingMaterial.content.isnot(None), MeetingMaterial.content != "")
            .all()
        )
        documents = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.content.isnot(None), KnowledgeDocument.content != ""
            )
            .all()
        )
        pending_materials = [
            row
            for row in materials
            if _needs_rebuild(
                row,
                fingerprint,
                chunk_repository.count_by_material(db, row.material_id),
                args.force,
            )
        ]
        pending_documents = [
            row
            for row in documents
            if _needs_rebuild(
                row,
                fingerprint,
                knowledge_chunk_repository.count_by_document(db, row.document_id),
                args.force,
            )
        ]
        print(
            f"待重建：materials={len(pending_materials)}/{len(materials)} "
            f"knowledge_documents={len(pending_documents)}/{len(documents)}"
        )
        if args.dry_run:
            return 0

        settings_dir = settings.storage_dir
        for material in pending_materials:
            rows = indexing_service.index_material(db, material)
            material.content_hash = material.content_hash or _hash_stored(
                settings_dir, material.storage_key
            )
            material.index_fingerprint = fingerprint
            material.indexed_at = utc_now()
            db.commit()
            print(f"  [material]   {material.material_id} chunks={len(rows)}")
        for document in pending_documents:
            knowledge_service._index_document(db, document)
            document.content_hash = document.content_hash or _hash_stored(
                settings_dir, document.storage_key
            )
            document.index_fingerprint = fingerprint
            document.indexed_at = utc_now()
            db.commit()
            print(f"  [knowledge]  {document.document_id}")
        print("重建完成。")
        return 0
    finally:
        db.close()


def _hash_stored(settings_dir: str, storage_key: str) -> str | None:
    """从磁盘原文件回填内容摘要；文件丢失时返回 None（保持 NULL）。"""
    try:
        return file_sha256(storage.read_bytes(settings_dir, storage_key))
    except OSError:
        return None


if __name__ == "__main__":
    sys.exit(main())
