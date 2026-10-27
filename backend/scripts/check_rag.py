from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_ai import EXIT_CONFIG, EXIT_FAIL, EXIT_OK, config_missing  # noqa: E402

from app.ai.chat import ChatService  # noqa: E402
from app.ai.embeddings import EmbeddingClient  # noqa: E402
from app.ai.extraction import ActionItemExtractor, IssueExtractor  # noqa: E402
from app.ai.indexing import split_text  # noqa: E402
from app.ai.llm import LLMClient  # noqa: E402
from app.ai.minutes import MinutesService  # noqa: E402
from app.ai.parsers import parse_bytes  # noqa: E402
from app.ai.preparation import PreparationService  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402

SAMPLE_TEXT = """\
OpenMIND「年轮」项目第三次周会

时间：2026年10月8日 14:00-15:10
参会：陈福明（A，系统后端负责人）、赵程程（B，AI 后端）、潘丽萍（C，前端）
主持人：陈福明　记录：赵程程

一、上周进度回顾
陈福明：M00 工程基础九项任务已全部验收，CI 全绿。设计基线文档已经合并，后续所有模块
的表结构以 database.md 为准，接口以 api.md 为准。
赵程程：AI 解析管线完成，支持 PDF、DOCX、TXT 三种格式，25 个单元测试全部通过。大模型
连通性验证完成，文本生成使用 deepseek-flash，向量使用百炼 text-embedding-v3，1024 维。
潘丽萍：认证页面第一版完成，包含注册、登录、退出三个流程，等待发起 PR。

二、本周计划与风险
陈福明：会议管理的数据库表还没建，M02 会议表、M03 材料表、M04 分块表统一由我在
10月15日之前交付，字段严格按 database.md 执行。这是当前最大的进度风险，AI 的向量入库
和检索功能都在等这三张表。
赵程程：向量入库和 RAG 检索依赖 document_chunks 表，表一到我两天内接完。目前四个功能
分支已经提交 PR，按顺序等待评审合并。
潘丽萍：会议列表和创建会议页面本周开始开发，依赖后端接口契约先定稿。

三、讨论与决定
1. 数据库表由陈福明在10月15日前统一交付，包含会议、材料、分块三张表。
2. 功能分支按 PR 序号顺序合并：先基础客户端，再切分器，最后编排层。
3. 前端接口以 docs/api.md 为唯一事实来源，8 个待确认接口在本周例会上敲定。
4. 演示版本在10月30日冻结功能，冻结之后只允许修复缺陷，不再新增功能。

四、待解决的问题
1. 分块表向量列的检索索引方案未定，pgvector 的 HNSW 索引参数需要实测后确认。
2. 模型输出偶尔为空，推理模式下 max_tokens 过小会导致正文丢失，需要统一最小取值。
3. 跨用户越权测试由谁编写尚未确定，建议 A 负责路由层、B 负责检索层，本周内确认。
"""

NOISE_QUESTION = "公司去年的营业收入是多少？"

REFUSAL_MARKERS = (
    "无法确认",
    "无法回答",
    "无法依据",
    "材料中没有",
    "没有关于",
    "不足以",
    "没有提供",
    "不包含",
)


@dataclass(frozen=True)
class SmokeChunk:
    meeting_id: str
    material_id: str
    record_id: str | None
    excerpt: str
    score: float


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if not norm_left or not norm_right:
        return 0.0
    return dot / (norm_left * norm_right)


class InMemoryRetriever:
    def __init__(
        self,
        excerpts: list[str],
        vectors: list[list[float]],
        embedder: EmbeddingClient,
    ) -> None:
        self.excerpts = excerpts
        self.vectors = vectors
        self.embedder = embedder

    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[SmokeChunk]:
        query_vector = self.embedder.embed([query])[0]
        scored: list[tuple[float, str]] = []
        for excerpt, vector in zip(self.excerpts, self.vectors, strict=True):
            score = cosine(query_vector, vector)
            if score >= min_score:
                scored.append((score, excerpt))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            SmokeChunk(
                meeting_id="smoke-meeting",
                material_id="smoke-material",
                record_id=None,
                excerpt=excerpt,
                score=round(score, 4),
            )
            for score, excerpt in scored[:top_k]
        ]


def stage(title: str) -> None:
    print(f"== {title} ==")


def passed(message: str) -> None:
    print(f"[OK]   {message}")
    print()


def failed(message: str) -> None:
    print(f"[FAIL] {message}")
    print()


def run_full(llm: LLMClient, text: str, topic: str) -> bool:
    transcripts = [text]
    try:
        minutes = MinutesService(llm).generate(topic, transcripts)
    except AppError as exc:
        failed(f"纪要生成失败 {exc.error_code}：{exc.message}")
        return False
    print("-- 会议纪要 --")
    print(minutes.strip())
    print()

    try:
        action_items = ActionItemExtractor(llm).extract(transcripts)
    except AppError as exc:
        failed(f"行动项提取失败 {exc.error_code}：{exc.message}")
        return False
    print(f"-- 候选行动项（{len(action_items)} 条）--")
    for item in action_items:
        assignee = item.assignee or "未指定"
        due = item.due_date or "无截止"
        print(f"- {item.content} | 负责人={assignee} | 截止={due}")
    print()

    try:
        issues = IssueExtractor(llm).extract(transcripts)
    except AppError as exc:
        failed(f"问题提取失败 {exc.error_code}：{exc.message}")
        return False
    print(f"-- 候选问题（{len(issues)} 条）--")
    for issue in issues:
        follow_up = issue.follow_up or "无跟进"
        print(f"- {issue.description} | 跟进={follow_up}")
    print()

    try:
        draft = PreparationService(llm).generate(topic, [text])
    except AppError as exc:
        failed(f"会前准备生成失败 {exc.error_code}：{exc.message}")
        return False
    print("-- 会前准备摘要 --")
    print(draft.summary.strip())
    print(f"-- 准备清单（{len(draft.checklist)} 项）--")
    for entry in draft.checklist:
        print(f"- {entry}")
    print()

    if not action_items or not issues or not draft.checklist:
        failed("生成类检查至少一项结果为空，prompt 输出质量不达标")
        return False
    passed("纪要 / 行动项 / 问题 / 会前准备四类生成全部成功")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 全链路冒烟：解析→切分→向量化→检索→问答")
    parser.add_argument("--file", help="自备 txt 文件路径，缺省使用内置会议记录样例")
    parser.add_argument(
        "--question",
        default="会议决定由谁在什么时候交付数据库表？",
        help="应当命中分块的相关问题",
    )
    parser.add_argument("--full", action="store_true", help="追加纪要/行动项/问题/会前准备检查")
    parser.add_argument("--top-k", type=int, default=5, help="检索返回的最大分块数")
    parser.add_argument("--min-score", type=float, default=0.3, help="相似度阈值")
    parser.add_argument("--timeout", type=float, default=60.0, help="LLM 单次请求超时秒数")
    args = parser.parse_args()

    config_issues = config_missing("llm") + config_missing("embedding")
    if config_issues:
        for issue in config_issues:
            print(f"[FAIL] {issue}")
        print()
        print("结论：配置缺失或仍为占位值，请填写 docker/.env 后重试。")
        return EXIT_CONFIG

    settings = get_settings()
    print(
        f"LLM_API_BASE={settings.llm_api_base}  LLM_MODEL={settings.llm_model}",
    )
    print(
        f"EMBEDDING_API_BASE={settings.embedding_api_base}  "
        f"EMBEDDING_MODEL={settings.embedding_model}  EMBEDDING_DIM={settings.embedding_dim}"
    )
    print(f"检索参数 top_k={args.top_k} min_score={args.min_score}")
    print("密钥仅在服务端使用，本脚本不打印密钥内容。")
    print()

    if args.file:
        file_path = Path(args.file)
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            failed(f"读取文件失败：{exc}")
            return EXIT_FAIL
        file_name = file_path.name
    else:
        data = SAMPLE_TEXT.encode("utf-8")
        file_name = "smoke-meeting.txt"

    llm = LLMClient()
    embedder = EmbeddingClient()

    stage("1/4 解析")
    try:
        document = parse_bytes(data, file_name)
    except AppError as exc:
        failed(f"{exc.error_code}：{exc.message}")
        return EXIT_FAIL
    passed(f"parser={document.parser} 文件={document.file_name} 字符数={len(document.content)}")

    stage("2/4 切分")
    excerpts = split_text(document.content, chunk_size=800, overlap=120)
    if not excerpts:
        failed("切分结果为空")
        return EXIT_FAIL
    passed(
        f"chunk_size=800 overlap=120 分块数={len(excerpts)} "
        f"最长={max(len(chunk) for chunk in excerpts)}"
    )

    stage("3/4 向量化")
    try:
        vectors = embedder.embed(excerpts)
    except AppError as exc:
        failed(f"{exc.error_code}：{exc.message}")
        return EXIT_FAIL
    passed(f"model={embedder.model} 维度={len(vectors[0])} 条数={len(vectors)}")

    stage("4/4 检索问答")
    retriever = InMemoryRetriever(excerpts, vectors, embedder)
    chat = ChatService(llm, retriever)

    raw_hits = retriever.retrieve(
        args.question,
        user_id="smoke-user",
        top_k=args.top_k,
        min_score=0.0,
    )
    for hit in raw_hits[:3]:
        print(f"       候选分数 {hit.score}　{hit.excerpt[:40]}...")
    try:
        answer = chat.answer(args.question, user_id="smoke-user")
    except AppError as exc:
        failed(f"{exc.error_code}：{exc.message}")
        return EXIT_FAIL
    if answer.insufficient_evidence:
        failed(f"相关问题未命中任何分块：{args.question}（可调低 --min-score 观察分数）")
        return EXIT_FAIL
    print(f"       问题：{args.question}")
    print(f"       回答：{answer.answer.strip()}")
    print(f"       来源分块数：{len(answer.sources)}")
    print()

    noise_hits = retriever.retrieve(
        NOISE_QUESTION,
        user_id="smoke-user",
        top_k=3,
        min_score=0.0,
    )
    noise_top = noise_hits[0].score if noise_hits else 0.0
    try:
        noise = chat.answer(NOISE_QUESTION, user_id="smoke-user")
    except AppError as exc:
        failed(f"{exc.error_code}：{exc.message}")
        return EXIT_FAIL
    if noise.insufficient_evidence:
        passed(
            f"相关问题命中来源并生成回答；无关问题被 min_score 拦截（最高分 {noise_top}）"
        )
    elif any(marker in noise.answer for marker in REFUSAL_MARKERS):
        print(f"       无关问题：{NOISE_QUESTION}")
        print(f"       拒答：{noise.answer.strip()[:120]}")
        print()
        passed(
            f"相关问题命中来源并生成回答；无关问题由回答防线拒绝"
            f"（候选最高分 {noise_top} 高于 min_score，属已知的分数聚集现象）"
        )
    else:
        failed(
            f"无关问题既未被阈值拦截也未被拒绝（候选最高分 {noise_top}）："
            f"{noise.answer.strip()[:150]}"
        )
        return EXIT_FAIL

    if not args.full:
        print("全部通过：AI 全链路（解析→切分→向量化→检索→问答）冒烟成功。")
        return EXIT_OK

    stage("附加/4 生成类 prompt 质量")
    topic = "OpenMIND 年轮项目第三次周会"
    started = time.monotonic()
    if not run_full(llm, document.content, topic):
        return EXIT_FAIL
    passed(f"四类生成全部成功，耗时={int(time.monotonic() - started)}s")
    print("全部通过：AI 全链路与生成类 prompt 冒烟成功。")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
