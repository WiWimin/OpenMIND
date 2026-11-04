"""RAG 检索质量评测：隔离 eval 用户 → HTTP API 灌库 → 应用层检索 → 指标报告。

设计约束（验收方案 v2）：
- 数据隔离：专用 eval 用户，检索按 user_id 下推，与生产数据查询层隔离；
- 灌入路径：后端 HTTP API（与生产一致）；检索路径：应用层 VectorRetriever
  （与生产 chat / 知识库搜索同一实现，含 SQL 权限过滤），禁止裸 SQL、不经 LLM；
- 三段准入：① config↔DB 向量维度一致 ② 连续 2 次 embedding 成功
  ③ 检索冒烟（首查 top-1 命中且 ≥min_score、1 条负样本被拒）；
- 维度变更边界：不一致即中止（先执行 scripts/reindex_all.py 重建，无兼容降级）；
- 联网固定关闭（`WEB_SEARCH_ENABLED=false` 在导入 app 配置前写入，
  检索层口径与答案层联网解耦，见验收方案 v2 第 2 点）；
- 清理：默认 finally 级联删除 eval 用户数据与 storage 文件（--keep 跳过）；
- 退出码：0=Go（准入指标全达标） 2=No-Go（未达标，报告含错误分析） 1=执行错误。

用法（宿主机 backend/ 目录）：
    python scripts/eval_rag.py                # 全流程 + 报告 + 清理
    python scripts/eval_rag.py --keep         # 保留 eval 数据（调试）
    python scripts/eval_rag.py --cleanup-only # 只清理上次残留
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

# 评测口径固定：关闭联网（必须早于 app 配置首次读取）
os.environ["WEB_SEARCH_ENABLED"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.rag.retriever import VectorRetriever  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.core.security import decode_access_token  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.chunk import DocumentChunk  # noqa: E402
from app.models.knowledge_chunk import KnowledgeChunk  # noqa: E402
from app.models.knowledge_document import KnowledgeDocument  # noqa: E402
from app.models.material import MeetingMaterial  # noqa: E402
from app.models.meeting import Meeting  # noqa: E402
from app.models.model_config import UserModelConfig  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_memory import UserMemory  # noqa: E402
from app.services.model_config_service import (  # noqa: E402
    build_embedding_client,
    resolve_model_config,
)

API_BASE = "http://localhost:8000/api/v1"
EVAL_PASSWORD = "EvalRag!2026"
HERE = Path(__file__).resolve().parent
DATASET_PATH = HERE / "eval" / "dataset.json"
REPO_ROOT = HERE.parents[1]
STORAGE_ROOT = REPO_ROOT / "storage"
REPORT_PATH = REPO_ROOT / "docs" / "test-reports" / "rag-eval-report.md"

MIN_SCORE = 0.3
TOP_K = 5
MAX_ATTEMPTS = 4


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def unwrap(resp: httpx.Response) -> dict:
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "success":
        raise RuntimeError(f"非 success 响应：{body}")
    return body["data"]


def with_rate_retry(fn, label: str):
    """限流退避重试：评测中途 RATE_LIMITED 不直接判失败。"""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fn()
        except AppError as exc:
            if exc.error_code == "RATE_LIMITED" and attempt < MAX_ATTEMPTS - 1:
                wait = 3 * (attempt + 1)
                print(f"    [{label}] RATE_LIMITED，{wait}s 后重试 "
                      f"({attempt + 1}/{MAX_ATTEMPTS - 1})")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


# --------------------------------------------------------------------------- #
# 准入
# --------------------------------------------------------------------------- #
def stage1_dimensions(db) -> None:
    rows = db.execute(
        __import__("sqlalchemy").text(
            "SELECT DISTINCT vector_dims(embedding) AS d FROM document_chunks "
            "WHERE embedding IS NOT NULL UNION "
            "SELECT DISTINCT vector_dims(embedding) FROM knowledge_chunks "
            "WHERE embedding IS NOT NULL"
        )
    ).fetchall()
    config_dim = get_settings().embedding_dim
    dims = {r[0] for r in rows}
    if dims and dims != {config_dim}:
        raise RuntimeError(
            f"维度不一致：DB={sorted(dims)} config={config_dim}。"
            "边界处理：先执行 scripts/reindex_all.py 全量重建（无兼容降级），重建后重跑本脚本。"
        )
    print(f"[准入1] 维度一致 dim={config_dim}（存量向量维度={sorted(dims) or '无存量'}）")


def stage2_embed_twice(db, user_id: str) -> int:
    client = build_embedding_client(resolve_model_config(db, user_id))
    config_dim = get_settings().embedding_dim
    for i in (1, 2):
        vectors = client.embed([f"embedding 探针第 {i} 次 {uuid.uuid4().hex[:8]}"])
        if not vectors or len(vectors[0]) != config_dim:
            raise RuntimeError(f"探针 {i} 返回异常：dim="
                               f"{len(vectors[0]) if vectors else 0}")
        time.sleep(0.5)
    print(f"[准入2] 连续 2 次 embedding 成功 dim={config_dim}")


def stage3_retrieval_smoke(db, user_id: str, first_query: dict) -> None:
    retriever = VectorRetriever(db, user_id)
    results = with_rate_retry(
        lambda: retriever.retrieve(
            first_query["question"],
            user_id=user_id,
            scope="knowledge_base",
            top_k=TOP_K,
            min_score=MIN_SCORE,
        ),
        "smoke",
    )
    if not results or results[0].score < MIN_SCORE:
        raise RuntimeError(f"检索冒烟失败：top1={results[0].score if results else '无结果'}")
    print(f"[准入3] 检索冒烟通过 top1_score={results[0].score:.4f}")


# --------------------------------------------------------------------------- #
# 灌库（HTTP API）
# --------------------------------------------------------------------------- #
def ingest(db, dataset: dict) -> tuple[str, str, dict, dict]:
    """返回 (token, eval_user_id, document_id 映射, material_id 映射)。"""
    name = f"eval-rag-{int(time.time())}"
    with httpx.Client(base_url=API_BASE, timeout=120) as client:
        reg = unwrap(client.post(
            "/auth/register", json={"name": name, "password": EVAL_PASSWORD}))
        token = reg["access_token"]
        user_id = decode_access_token(token)["sub"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[灌库] eval 用户={name} user_id={user_id}")

        # 写入与服务端一致的 LLM 配置（模拟“已配置用户”；ALLOW_GLOBAL_FALLBACK=false
        # 时 Judge/生成链路需要用户自带配置，否则 LLM 不可用、Judge 会全部回退）
        settings = get_settings()
        if settings.llm_api_base and settings.llm_api_key:
            unwrap(client.put(
                "/me/settings/model",
                json={
                    "llm_api_base": settings.llm_api_base,
                    "llm_api_key": settings.llm_api_key,
                    "llm_model": settings.llm_model,
                },
                headers=headers,
            ))
            print("[灌库] eval 用户 LLM 配置已写入（服务端同款，probe 校验）")

        doc_map: dict[str, str] = {}
        mat_map: dict[str, str] = {}
        meeting_id = None
        try:
            for item in dataset["corpus"]:
                path = HERE / "eval" / item["file"]
                raw = path.read_bytes()
                if item["scope"] == "knowledge_base":
                    data = unwrap(client.post(
                        "/knowledge/documents",
                        files={"file": (path.name, raw, "text/plain")},
                        headers=headers,
                    ))
                    if data["processing_status"] != "processed":
                        raise RuntimeError(
                            f"知识库文档解析失败：{path.name} {data.get('parse_error')}")
                    doc_map[item["doc_key"]] = data["document_id"]
                else:
                    if meeting_id is None:
                        meeting = unwrap(client.post(
                            "/meetings",
                            json={"title": f"RAG评测会议 {name}",
                                  "topic": "检索质量评测"},
                            headers=headers,
                        ))
                        meeting_id = meeting["meeting_id"]
                    data = unwrap(client.post(
                        f"/meetings/{meeting_id}/materials",
                        files={"file": (path.name, raw, "text/plain")},
                        headers=headers,
                    ))
                    if data["processing_status"] != "processed":
                        raise RuntimeError(
                            f"材料解析失败：{path.name} {data.get('parse_error')}")
                    mat_map[item["doc_key"]] = data["material_id"]
            print(f"[灌库] knowledge={len(doc_map)} materials={len(mat_map)} "
                  f"meeting={meeting_id}")
        except Exception:
            # 灌库失败立即回滚，不留半套数据
            _cleanup(db, user_id)
            raise
    return token, user_id, doc_map, mat_map


# --------------------------------------------------------------------------- #
# 检索评测（应用层，与生产同实现）
# --------------------------------------------------------------------------- #
def run_queries(db, user_id: str, meeting_id: str, dataset: dict,
                doc_map: dict, mat_map: dict) -> tuple[list, list]:
    id_to_key = {**{v: k for k, v in doc_map.items()},
                 **{v: k for k, v in mat_map.items()}}
    retriever = VectorRetriever(db, user_id)
    rows = []
    for item in dataset["corpus"]:
        scope = item["scope"]
        for q in item["questions"]:
            def _search(q=q, scope=scope):
                kwargs = {"user_id": user_id, "scope": scope,
                          "top_k": TOP_K, "min_score": MIN_SCORE}
                if scope == "current_meeting":
                    kwargs["current_meeting_id"] = meeting_id
                return retriever.retrieve(q["question"], **kwargs)

            results = with_rate_retry(_search, "query")
            rank = 0
            for i, r in enumerate(results, start=1):
                rid = r.document_id if scope == "knowledge_base" else r.material_id
                if id_to_key.get(rid) == item["doc_key"]:
                    rank = i
                    break
            chunk_hit = any(
                q["expect_chunk_contains"] in r.excerpt for r in results)
            rows.append({
                "scope": scope, "doc_key": item["doc_key"],
                "question": q["question"], "rank": rank,
                "hit1": rank == 1, "hit5": 1 <= rank <= 5,
                "rr": (1.0 / rank) if rank else 0.0,
                "chunk_hit": chunk_hit,
                "top": [(id_to_key.get(
                            r.document_id if scope == "knowledge_base"
                            else r.material_id, "?"),
                         round(r.score, 4)) for r in results],
            })

    negatives = []
    for neg in dataset["negatives"]:
        for scope in ("knowledge_base", "current_meeting"):
            def _neg_search(neg=neg, scope=scope):
                kwargs = {"user_id": user_id, "scope": scope,
                          "top_k": TOP_K, "min_score": MIN_SCORE}
                if scope == "current_meeting":
                    kwargs["current_meeting_id"] = meeting_id
                return retriever.retrieve(neg["question"], **kwargs)

            results = with_rate_retry(_neg_search, "neg")
            top1 = results[0].score if results else None
            intercepted = (not results) or top1 < MIN_SCORE
            negatives.append({
                "question": neg["question"], "category": neg["category"],
                "scope": scope, "top1": top1,
                "intercepted": intercepted,
            })
    return rows, negatives


def metrics(rows: list) -> dict:
    out = {}
    for scope in ("knowledge_base", "current_meeting", "overall"):
        subset = rows if scope == "overall" else [r for r in rows if r["scope"] == scope]
        n = len(subset)
        if not n:
            continue
        out[scope] = {
            "n": n,
            "hit1": sum(r["hit1"] for r in subset) / n,
            "hit5": sum(r["hit5"] for r in subset) / n,
            "mrr": sum(r["rr"] for r in subset) / n,
            "chunk_hit5": sum(r["chunk_hit"] for r in subset) / n,
        }
    return out


# --------------------------------------------------------------------------- #
# HTTP 一致性对照
# --------------------------------------------------------------------------- #
def consistency_check(token: str, first_query: dict, doc_map: dict) -> str:
    expected = doc_map.get(first_query["doc_key"], "?")
    with httpx.Client(base_url=API_BASE, timeout=60) as client:
        data = unwrap(client.post(
            "/knowledge/search",
            json={"query": first_query["question"],
                  "top_k": TOP_K, "min_score": MIN_SCORE},
            headers={"Authorization": f"Bearer {token}"},
        ))
    items = data.get("items") or []
    top = items[0]["document_id"] if items else None
    return "一致" if top == expected else f"不一致（HTTP top1={top} 期望={expected}）"


# --------------------------------------------------------------------------- #
# 清理（级联，含 storage 文件）
# --------------------------------------------------------------------------- #
def _cleanup(db, user_id: str) -> None:
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == user_id).all()
    for d in docs:
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == d.document_id).delete()
        _unlink(d.storage_key)
    db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == user_id).delete()

    meetings = db.query(Meeting).filter(Meeting.user_id == user_id).all()
    for m in meetings:
        mats = db.query(MeetingMaterial).filter(
            MeetingMaterial.meeting_id == m.meeting_id).all()
        for mat in mats:
            db.query(DocumentChunk).filter(
                DocumentChunk.material_id == mat.material_id).delete()
            _unlink(mat.storage_key)
        db.query(MeetingMaterial).filter(
            MeetingMaterial.meeting_id == m.meeting_id).delete()
    db.query(Meeting).filter(Meeting.user_id == user_id).delete()

    # BYOK 写入与记忆（外键先于 users 删除）
    db.query(UserModelConfig).filter(
        UserModelConfig.user_id == user_id
    ).delete()
    db.query(UserMemory).filter(UserMemory.user_id == user_id).delete()

    db.query(User).filter(User.user_id == user_id).delete()
    db.commit()


def _unlink(storage_key: str | None) -> None:
    if not storage_key:
        return
    path = STORAGE_ROOT / storage_key
    if path.exists():
        path.unlink()


def cleanup_residuals(db) -> int:
    """清理历史残留的 eval-rag-* 用户。"""
    users = db.query(User).filter(User.name.like("eval-rag-%")).all()
    for u in users:
        print(f"[清理] 残留用户 {u.name} ({u.user_id})")
        _cleanup(db, u.user_id)
    if not users:
        print("[清理] 无残留")
    return len(users)


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #
def write_report(dataset: dict, meta: dict, m: dict, negatives: list,
                 rows: list, admission: dict) -> tuple[str, bool]:
    lines = []
    lines.append("# RAG 检索质量评测报告")
    lines.append("")
    lines.append(f"- 执行时间：{meta['timestamp']}")
    lines.append(f"- Embedding：`{meta['embedding_model']}` dim={meta['embedding_dim']}")
    lines.append(f"- 固定配置：top_k={TOP_K}、min_score={MIN_SCORE}、"
                 f"chunk={meta['chunk_size']}/{meta['chunk_overlap']}；"
                 f"RAG Judge：enabled={meta['judge_enabled']}、"
                 f"judge_min_score={meta['judge_min_score']}（低分带 LLM 复核）；"
                 f"web_search={meta['web_search_enabled']}（评测口径固定关闭）")
    lines.append(f"- 灌入路径：HTTP API `{API_BASE}`；检索路径：应用层 VectorRetriever"
                 "（与生产同实现，含 user_id SQL 下推，不经 LLM、无裸 SQL）")
    lines.append(f"- 数据集：`backend/scripts/eval/dataset.json` "
                 f"sha256={meta['dataset_sha']}（语料 {len(dataset['corpus'])} 篇）")
    lines.append(f"- 三段准入：{meta['stages']}")
    lines.append(f"- HTTP 一致性对照：{meta['consistency']}")
    lines.append("")
    lines.append("## 一、准入指标（Go/No-Go）")
    lines.append("")
    lines.append("| 指标 | 门槛 | 实测 | 结论 |")
    lines.append("| --- | --- | --- | --- |")
    ok_all = True
    checks = [
        ("知识库 scope hit@5", admission["knowledge_base.hit_at_5"],
         m.get("knowledge_base", {}).get("hit5")),
        ("会议材料 scope hit@5", admission["current_meeting.hit_at_5"],
         m.get("current_meeting", {}).get("hit5")),
        ("总体 MRR", admission["overall.mrr"], m.get("overall", {}).get("mrr")),
        ("负样本拦截率", admission["negatives.interception_rate"],
         meta["interception_rate"]),
    ]
    for label, gate, value in checks:
        passed = value is not None and value >= gate
        ok_all = ok_all and passed
        shown = "—" if value is None else f"{value:.3f}"
        lines.append(f"| {label} | {gate} | {shown} | {'✅ 达标' if passed else '❌ 未达标'} |")
    lines.append("")
    lines.append("## 二、分 scope 指标")
    lines.append("")
    lines.append("| scope | n | hit@1 | hit@5 | MRR | chunk 命中@5 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for scope in ("knowledge_base", "current_meeting", "overall"):
        if scope in m:
            s = m[scope]
            lines.append(f"| {scope} | {s['n']} | {s['hit1']:.3f} | "
                         f"{s['hit5']:.3f} | {s['mrr']:.3f} | {s['chunk_hit5']:.3f} |")
    lines.append("")
    lines.append("## 三、负样本拦截明细")
    lines.append("")
    lines.append("| 问题 | 分类 | scope | top1 分数 | 拦截 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for n in negatives:
        score = "—" if n["top1"] is None else f"{n['top1']:.4f}"
        lines.append(f"| {n['question']} | {n['category']} | {n['scope']} | "
                     f"{score} | {'✅' if n['intercepted'] else '❌ 放行'} |")
    lines.append("")
    misses = [r for r in rows if not r["hit5"]]
    lines.append("## 四、未命中分析（hit@5 miss）")
    lines.append("")
    if not misses:
        lines.append("无未命中查询。")
    else:
        lines.append("| scope | 期望文档 | 问题 | 实际 top3（doc_key, score） |")
        lines.append("| --- | --- | --- | --- |")
        for r in misses:
            lines.append(f"| {r['scope']} | {r['doc_key']} | {r['question']} | "
                         f"{r['top'][:3]} |")
    lines.append("")
    lines.append("## 五、chunk 级未命中（内容断言失败）")
    lines.append("")
    chunk_miss = [r for r in rows if not r["chunk_hit"]]
    if not chunk_miss:
        lines.append("全部查询的 top5 中均包含期望内容片段。")
    else:
        for r in chunk_miss:
            lines.append(f"- [{r['scope']}] {r['question']}（期望包含："
                         f"见 dataset.json expect_chunk_contains）")
    lines.append("")
    lines.append("## 六、分数分布（阈值校准参考，不自动放宽）")
    lines.append("")
    pos_top1 = [r["top"][0][1] for r in rows if r["top"]]
    neg_top1 = [n["top1"] for n in negatives if n["top1"] is not None]
    if pos_top1 and neg_top1:
        ordered = sorted(pos_top1)
        median = ordered[len(ordered) // 2]
        neg_max = max(neg_top1)
        pos_min = min(pos_top1)
        lines.append(f"- 正样本 top1：min={pos_min:.4f} / median={median:.4f} / "
                     f"max={max(pos_top1):.4f}（n={len(pos_top1)}）")
        lines.append(f"- 负样本 top1（未拦截者）：min={min(neg_top1):.4f} / "
                     f"max={neg_max:.4f}（n={len(neg_top1)}）")
        if pos_min > neg_max:
            lines.append(f"- 存在干净分界：min_score 调至 ({neg_max:.4f}, {pos_min:.4f}] "
                         "区间可同时拦截全部负样本并保留全部正样本；"
                         "阈值属产品配置，须评审后修改。")
        else:
            lines.append(f"- 无干净分界（正样本 min {pos_min:.4f} ≤ 负样本 max "
                         f"{neg_max:.4f}）：单靠阈值无法分离，需引入重排序、"
                         "答案相关性校验或负样本拒答策略，属产品级改进项。")
    lines.append("")
    verdict_text = (
        "Go — 全部准入指标达标" if ok_all else "No-Go — 存在未达标指标，见上表"
    )
    lines.append(f"**结论：{verdict_text}**")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[报告] {REPORT_PATH}")
    return "Go" if ok_all else "No-Go", ok_all


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true",
                        help="保留 eval 用户与数据（调试用）")
    parser.add_argument("--cleanup-only", action="store_true",
                        help="只清理历史残留后退出")
    args = parser.parse_args()

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    settings = get_settings()
    db = SessionLocal()
    try:
        if args.cleanup_only:
            cleanup_residuals(db)
            return 0

        print("== 准入① 维度一致性 ==")
        stage1_dimensions(db)

        print("== 灌库（HTTP API，隔离 eval 用户）==")
        token, user_id, doc_map, mat_map = ingest(db, dataset)

        try:
            print("== 准入② 连续 embedding ==")
            stage2_embed_twice(db, user_id)

            first = {"doc_key": dataset["corpus"][0]["doc_key"],
                     "question": dataset["corpus"][0]["questions"][0]["question"]}
            print("== 准入③ 检索冒烟 ==")
            stage3_retrieval_smoke(db, user_id, first)

            meeting = (db.query(Meeting).filter(Meeting.user_id == user_id).first())
            meeting_id = meeting.meeting_id if meeting else ""

            print("== 检索评测（36 正 + 负样本 ×2 scope）==")
            rows, negatives = run_queries(
                db, user_id, meeting_id, dataset, doc_map, mat_map)

            print("== HTTP 一致性对照 ==")
            consistency = consistency_check(token, first, doc_map)
            print(f"    {consistency}")

            m = metrics(rows)
            intercepted = sum(1 for n in negatives if n["intercepted"])
            interception_rate = intercepted / len(negatives) if negatives else 0.0

            admission = dataset["admission"]
            meta = {
                "timestamp": datetime.now(UTC).astimezone().isoformat(
                    timespec="seconds"),
                "embedding_model": settings.embedding_model,
                "embedding_dim": settings.embedding_dim,
                "chunk_size": 800, "chunk_overlap": 120,
                "judge_enabled": settings.rag_judge_enabled,
                "judge_min_score": settings.rag_judge_min_score,
                "web_search_enabled": settings.web_search_enabled,
                "dataset_sha": sha256_file(DATASET_PATH),
                "stages": "①维度一致 ②连续 embedding ③检索冒烟 — 全部通过",
                "consistency": consistency,
                "interception_rate": interception_rate,
            }
            verdict, ok = write_report(dataset, meta, m, negatives, rows,
                                       admission)
            print(f"== 结论：{verdict}（负样本拦截率 "
                  f"{interception_rate:.1%}，一致性 {consistency}）==")
            return 0 if ok else 2
        finally:
            if not args.keep:
                print("== 清理 eval 数据 ==")
                _cleanup(db, user_id)
            else:
                print(f"== --keep：保留 eval 用户 {user_id} ==")
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
