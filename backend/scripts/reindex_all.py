"""全量重建向量索引。

用途：embedding 模型或维度变更后，把已有会议材料与知识库文档重新向量化，
使存量向量与新模型处于同一向量空间（同维不同模型同样不可比）。

用法：
    python scripts/reindex_all.py --dry-run   # 只统计，不写入
    python scripts/reindex_all.py             # 重建并提交
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.models.knowledge_document import KnowledgeDocument  # noqa: E402
from app.models.material import MeetingMaterial  # noqa: E402
from app.services import indexing_service, knowledge_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只统计待重建对象，不写入")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        materials = (
            db.query(MeetingMaterial)
            .filter(MeetingMaterial.content.isnot(None), MeetingMaterial.content != "")
            .all()
        )
        documents = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.content.isnot(None), KnowledgeDocument.content != "")
            .all()
        )
        print(f"待重建：materials={len(materials)} knowledge_documents={len(documents)}")
        if args.dry_run:
            return 0

        for material in materials:
            rows = indexing_service.index_material(db, material)
            print(f"  [material]   {material.material_id} chunks={len(rows)}")
        for document in documents:
            knowledge_service._index_document(db, document)
            db.commit()
            print(f"  [knowledge]  {document.document_id}")
        print("重建完成。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
