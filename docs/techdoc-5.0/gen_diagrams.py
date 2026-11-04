# -*- coding: utf-8 -*-
"""Generate the five OpenMIND tech-doc 4.1 diagrams as .drawio + .svg.

Round 3 (supplemental): fix P0-1 (fig3-4 wrong PostgreSQL->external edges),
fig4-1 legend consistency, fig3-1 edge clipping, fig3-2 SQL/embedding order,
fig3-3 audio retry semantics. Self-validating: overflow/overlap/out-of-canvas.
"""
import html
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagrams")
os.makedirs(OUT, exist_ok=True)

F_LAYER = "#F8FAFC"
F_FRONT = "#E8F0F8"
F_AI = "#EAF2F0"
F_STORE = "#F1F5F9"
F_EXT = "#E8EEF6"
F_PLAN = "#FFFFFF"
STROKE = "#64748B"
STROKE_PLAN = "#94A3B8"
TEXT = "#1E293B"
NOTE = "#475569"
FONT = 'Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif'


def est(s, fs):
    w = 0.0
    for ch in s:
        w += fs if ord(ch) > 0x2E80 else fs * 0.55
    return w


class Box:
    def __init__(self, x, y, w, h, lines, fill=F_LAYER, stroke=STROKE, dashed=False,
                 title_size=22, body_size=18, bold_title=False, align="center"):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.lines = lines if isinstance(lines, list) else [lines]
        self.fill, self.stroke, self.dashed = fill, stroke, dashed
        self.title_size, self.body_size = title_size, body_size
        self.bold_title, self.align = bold_title, align


class Edge:
    def __init__(self, pts, label=None, dashed=False, label_pos=None, label_size=15):
        self.pts, self.label, self.dashed = pts, label, dashed
        self.label_pos, self.label_size = label_pos, label_size


def esc(s):
    return html.escape(s, quote=True)


def svg_text_lines(b, cx, cy):
    out = []
    n = len(b.lines)
    sizes = [b.title_size] + [b.body_size] * (n - 1)
    weights = ["700" if b.bold_title else "400"] + ["400"] * (n - 1)
    line_h = max(b.title_size, b.body_size) + 7
    total = n * line_h
    y0 = cy - total / 2 + line_h / 2
    anchor = "middle" if b.align == "center" else "start"
    x = cx if b.align == "center" else b.x + 12
    for i, ln in enumerate(b.lines):
        out.append(
            f'<text x="{x:.1f}" y="{y0 + i * line_h:.1f}" font-family="{FONT}" '
            f'font-size="{sizes[i]}" font-weight="{weights[i]}" fill="{TEXT}" '
            f'text-anchor="{anchor}" dominant-baseline="middle">{esc(ln)}</text>'
        )
    return "".join(out)


def render_svg(d, w, h, legend_lines=None):
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}" font-family="{FONT}">']
    p.append('<defs><marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="3" '
             'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,3 L0,6 z" fill="%s"/></marker></defs>' % STROKE)
    p.append('<defs><marker id="arrP" markerWidth="10" markerHeight="10" refX="8" refY="3" '
             'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,3 L0,6 z" fill="%s"/></marker></defs>' % STROKE_PLAN)
    for b in d.boxes:
        dashes = ' stroke-dasharray="8 6"' if b.dashed else ""
        p.append(f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="8" '
                 f'fill="{b.fill}" stroke="{b.stroke}" stroke-width="1.6"{dashes}/>')
        p.append(svg_text_lines(b, b.x + b.w / 2, b.y + b.h / 2))
    for e in d.edges:
        marker = "arrP" if e.dashed else "arr"
        stroke = STROKE_PLAN if e.dashed else STROKE
        dash = ' stroke-dasharray="7 5"' if e.dashed else ""
        path = f"M {e.pts[0][0]},{e.pts[0][1]}"
        for pt in e.pts[1:]:
            path += f" L {pt[0]},{pt[1]}"
        p.append(f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="1.6" '
                 f'marker-end="url(#{marker})"{dash}/>')
        if e.label:
            lx, ly = e.label_pos if e.label_pos else e.pts[len(e.pts) // 2]
            p.append(f'<text x="{lx}" y="{ly}" font-family="{FONT}" font-size="{e.label_size}" '
                     f'fill="{NOTE}" text-anchor="middle" dominant-baseline="middle">{esc(e.label)}</text>')
    if legend_lines:
        ly = h - 20
        x = 40
        p.append(f'<line x1="{x}" y1="{ly}" x2="{x+40}" y2="{ly}" stroke="{STROKE}" stroke-width="1.6"/>')
        p.append(f'<text x="{x+48}" y="{ly}" font-family="{FONT}" font-size="15" fill="{NOTE}">{esc(legend_lines[0])}</text>')
        if len(legend_lines) > 1:
            x2 = x + 320
            p.append(f'<line x1="{x2}" y1="{ly}" x2="{x2+40}" y2="{ly}" stroke="{STROKE_PLAN}" stroke-width="1.6" stroke-dasharray="7 5"/>')
            p.append(f'<text x="{x2+48}" y="{ly}" font-family="{FONT}" font-size="15" fill="{NOTE}">{esc(legend_lines[1])}</text>')
        if len(legend_lines) > 2:
            x3 = x2 + 300
            p.append(f'<line x1="{x3}" y1="{ly}" x2="{x3+40}" y2="{ly}" stroke="{STROKE}" stroke-width="1.6" stroke-dasharray="3 5"/>')
            p.append(f'<text x="{x3+48}" y="{ly}" font-family="{FONT}" font-size="15" fill="{NOTE}">{esc(legend_lines[2])}</text>')
    p.append('</svg>')
    return "".join(p)


def render_drawio(d, name, w, h):
    cells = ['<mxCell id="0"/><mxCell id="1" parent="0"/>']
    for i, b in enumerate(d.boxes):
        style = ("rounded=1;whiteSpace=wrap;html=1;"
                 f"fillColor={b.fill};strokeColor={b.stroke};fontColor={TEXT};fontSize={b.body_size};"
                 + ("dashed=1;" if b.dashed else ""))
        label = "&#10;".join(esc(l) for l in b.lines)
        cells.append(f'<mxCell id="b{i}" value="{label}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" as="geometry"/></mxCell>')
    for j, e in enumerate(d.edges):
        style = ("html=1;rounded=0;endArrow=block;endFill=1;"
                 f"strokeColor={STROKE_PLAN if e.dashed else STROKE};" + ("dashed=1;" if e.dashed else ""))
        cells.append(f'<mxCell id="e{j}" value="{esc(e.label) if e.label else ""}" style="{style}" edge="1" parent="1">'
                     f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    return ('<mxfile host="app.diagrams.net" version="24.0.0" type="device">'
            f'<diagram id="{name}" name="{name}">'
            f'<mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
            f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{w}" pageHeight="{h}" math="0" shadow="0">'
            f'<root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')


class Diagram:
    def __init__(self, boxes, edges):
        self.boxes, self.edges = boxes, edges


_problems = []


def validate(name, d, w, h):
    for i, b in enumerate(d.boxes):
        if b.x < 0 or b.y < 0 or b.x + b.w > w or b.y + b.h > h:
            _problems.append(f"{name}: box {i} out of canvas")
        for j, ln in enumerate(b.lines):
            fs = b.title_size if j == 0 else b.body_size
            if est(ln, fs) > b.w - 16:
                _problems.append(f"{name}: box '{b.lines[0][:14]}' text overflow ({ln[:24]})")
    for i in range(len(d.boxes)):
        for j in range(i + 1, len(d.boxes)):
            a, b = d.boxes[i], d.boxes[j]
            if a.x < b.x + b.w and a.x + a.w > b.x and a.y < b.y + b.h and a.y + a.h > b.y:
                _problems.append(f"{name}: overlap box{i}('{a.lines[0][:12]}') box{j}('{b.lines[0][:12]}')")


def write_diagram(name, w, h, boxes, edges, legend=None):
    d = Diagram(boxes, edges)
    validate(name, d, w, h)
    with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
        f.write(render_svg(d, w, h, legend))
    with open(os.path.join(OUT, f"{name}.drawio"), "w", encoding="utf-8") as f:
        f.write(render_drawio(d, name, w, h))
    print("wrote", name)


# ===================== FIG 3-1 architecture (fix edge clipping / ASR label) =====================
def fig31():
    w, h = 1600, 1140
    L, LW = 60, 1040
    RH, RW = 1220, 340
    boxes = [
        Box(L, 40, LW, 96, ["用户访问端", "浏览器（Browser）"], F_FRONT, bold_title=True),
        Box(L, 166, LW, 110, ["前端应用", "Vue 3 · TypeScript · Pinia · Vue Router", "页面 · 状态 · API 调用"], F_FRONT, bold_title=True),
        Box(L, 306, LW, 100, ["后端 API 层", "FastAPI · API Router · 认证 · 依赖注入"], F_LAYER, bold_title=True),
        Box(L, 436, LW, 150, ["业务服务层（单体后端）",
                              "会议 · 材料 · 记录 · 会前准备 · 问答 · 纪要 · 行动项",
                              "任务 · 问题 · 知识库 · 记忆 · 模型配置 · 模板 · 音频"], F_LAYER, bold_title=True),
        Box(L, 616, LW, 130, ["AI 能力层",
                              "LLM Client · Embedding Client · RAG Retriever",
                              "解析/切分 · 结构化输出 · ASR Client"], F_AI, bold_title=True),
        Box(L, 776, LW, 150, ["数据层",
                              "PostgreSQL + pgvector（业务表 · document_chunks · knowledge_chunks）",
                              "storage/ 本地文件"], F_STORE, bold_title=True),
        Box(RH, 40, RW, 86, ["外部 / 本地模型服务", "（按配置接入）"], F_EXT, bold_title=True),
        Box(RH, 156, RW, 86, ["外部 LLM", "/chat/completions"], F_EXT),
        Box(RH, 272, RW, 86, ["外部 Embedding", "/embeddings（1024 维）"], F_EXT),
        Box(RH, 388, RW, 86, ["外部 ASR", "/audio/transcriptions"], F_EXT),
        Box(RH, 504, RW, 86, ["本地 FunASR（可选）", "funasr-server · sensevoice · CPU"], F_EXT),
    ]
    cx = L + LW / 2
    edges = [
        Edge([(cx, 136), (cx, 166)]),
        Edge([(cx, 276), (cx, 306)]),
        Edge([(cx, 406), (cx, 436)]),
        Edge([(cx - 170, 586), (cx - 170, 616)]),
        Edge([(cx + 170, 586), (cx + 170, 616)]),
        Edge([(cx, 746), (cx, 776)]),
        Edge([(L + 100, 616), (L + 100, 776)], label="检索 / 索引", label_pos=(L + 210, 696)),
        Edge([(L + LW, 660), (RH, 199)], label="LLM", label_pos=(1160, 430)),
        Edge([(L + LW, 681), (RH, 315)], label="Embedding", label_pos=(1160, 498)),
        Edge([(L + LW, 702), (RH, 431)], label="ASR", label_pos=(1160, 566)),
        Edge([(L + LW, 723), (RH, 547)], label="ASR(本地)", label_pos=(1160, 635)),
    ]
    write_diagram("fig3-1-architecture", w, h, boxes, edges,
                  legend=["实线 = 当前实现", "系统为单体后端（非微服务）"])


# ===================== FIG 3-2 RAG flow (SQL candidates before query embedding) =====================
def fig32():
    w, h = 1560, 900
    boxes = [
        Box(40, 40, 150, 78, ["用户问题"], F_FRONT, bold_title=True),
        Box(40, 150, 230, 78, ["身份 / 权限上下文", "current_user.user_id"], F_LAYER, bold_title=True),
        Box(40, 260, 230, 78, ["选择 scope", "current_meeting", "knowledge_base"], F_LAYER, bold_title=True),

        Box(340, 40, 620, 190, ["检索泳道 A：会议材料",
                                "document_chunks → meeting_materials → meetings",
                                "SQL 过滤 meetings.user_id = current_user",
                                "（当前会议 scope 加 meeting_materials.meeting_id）"], F_STORE, bold_title=True, body_size=16),
        Box(340, 260, 620, 190, ["检索泳道 B：个人知识库",
                                 "knowledge_chunks → knowledge_documents",
                                 "SQL 过滤 knowledge_documents.user_id = current_user"], F_STORE, bold_title=True, body_size=16),
        Box(340, 480, 620, 78, ["query embedding（候选集生成后）", "Embedding 1024 维"], F_AI, bold_title=True, body_size=16),

        Box(1020, 200, 340, 120, ["应用层余弦相似度排序", "候选分块 × query 向量", "（非 pgvector ANN）"], F_AI, bold_title=True, body_size=16),
        Box(1020, 360, 340, 80, ["Top-K 筛选", "top_k=5 · min_score=0.3"], F_AI, bold_title=True, body_size=16),

        Box(1020, 480, 340, 150, ["Prompt 组装",
                                  "检索片段（泳道 A/B）",
                                  "最近会议记录（20 条 · ≤8000 字）",
                                  "用户记忆（memory_context_for, \"chat\"）"], F_LAYER, bold_title=True, body_size=15),
        Box(1020, 670, 340, 80, ["LLM", "OpenAI 兼容 /chat/completions"], F_EXT, bold_title=True),
        Box(1370, 670, 190, 80, ["answer + sources"], F_FRONT, bold_title=True, title_size=18),

        Box(40, 700, 900, 110, ["证据不足分支", "无片段且无会议记录 → 返回“证据不足”，不编造答案"], F_LAYER, bold_title=True),
    ]
    edges = [
        Edge([(190, 79), (190, 150)]),
        Edge([(155, 228), (155, 260)]),
        # scope -> 泳道A (top) / 泳道B (bottom) / query embedding
        Edge([(270, 299), (340, 299)], dashed=True, label="scope=current_meeting", label_pos=(305, 283)),
        Edge([(270, 299), (340, 355)], dashed=True, label="scope=knowledge_base", label_pos=(305, 420)),
        Edge([(270, 299), (340, 519)], dashed=True, label="（并行）", label_pos=(305, 505)),
        # lanes + embedding -> similarity
        Edge([(960, 135), (1020, 260)], label="候选分块", label_pos=(990, 175)),
        Edge([(960, 355), (1020, 260)]),
        Edge([(960, 519), (1020, 260)], label="query 向量", label_pos=(990, 400)),
        # similarity -> topk
        Edge([(1190, 320), (1190, 360)]),
        # topk -> prompt
        Edge([(1190, 440), (1190, 480)]),
        # prompt -> llm
        Edge([(1190, 630), (1190, 670)]),
        Edge([(1360, 710), (1400, 710)]),
        # 证据不足
        Edge([(1190, 300), (940, 755)], dashed=True, label="无片段且无记录", label_pos=(1080, 560)),
    ]
    write_diagram("fig3-2-rag-flow", w, h, boxes, edges,
                  legend=["实线 = 当前数据流", "虚线 = scope 分支 / 证据不足分支"])


# ===================== FIG 3-3 state machines (fix audio retry semantics) =====================
def state_card_boxes_edges(cx, cy, cw, ch, title, states, branches, note, boxlist, edgelist):
    boxlist.append(Box(cx, cy, cw, 36, [title], F_LAYER, bold_title=True, title_size=20))
    fs = 14
    widths = [max(est(s, fs) + 22, 72) for s in states]
    gap = 18
    total_w = sum(widths) + gap * (len(states) - 1)
    x = cx + (cw - total_w) / 2
    sy = cy + 58
    sh = 40
    centers = []
    for i, s in enumerate(states):
        boxlist.append(Box(x, sy, widths[i], sh, [s], F_STORE, title_size=fs))
        centers.append((x + widths[i] / 2, sy + sh / 2))
        x += widths[i] + gap
    for i in range(1, len(centers)):
        edgelist.append(Edge([(centers[i - 1][0] + widths[i - 1] / 2, centers[i - 1][1]),
                              (centers[i][0] - widths[i] / 2, centers[i][1])]))
    by = sy + sh + 26
    for (fi, blabel) in branches:
        bw = max(est(blabel, fs) + 20, 70)
        bx = centers[fi][0] - bw / 2
        boxlist.append(Box(bx, by, bw, 34, [blabel], "#FFFFFF", STROKE, dashed=True, title_size=fs))
        edgelist.append(Edge([(centers[fi][0], sy + sh), (centers[fi][0], by)], dashed=True))
    ny = cy + ch - 34
    boxlist.append(Box(cx + 10, ny, cw - 20, 30, [note], "#FFFFFF", STROKE_PLAN, dashed=True, title_size=14))


def fig33():
    w, h = 1500, 1020
    boxes, edges = [], []
    colx = [40, 770]
    cw = 690
    ch = 230
    rows = [40, 280, 520, 760]
    cards = [
        ("会议", ["scheduled", "archived"], [], "归档后只读 · 写操作 409"),
        ("材料", ["uploaded", "processing", "processed"], [(1, "failed")], "无重试端点 · 失败需重新上传"),
        ("音频", ["uploaded", "processing", "transcribed", "confirmed"], [(1, "failed")],
         "processing→failed；failed 经 retry_transcription 重新进入 processing"),
        ("纪要", ["draft", "confirmed"], [], "经用户确认"),
        ("准备稿", ["draft", "confirmed"], [], "schema 含 generating/failed，服务仅用 draft/confirmed"),
        ("行动项", ["pending_confirmation", "confirmed", "converted"], [], "仅已确认可转任务 · 已转换不可删除"),
        ("问题", ["open", "resolved"], [(0, "cancelled")], "open → resolved / cancelled"),
        ("任务", ["todo", "in_progress", "completed"], [(0, "cancelled"), (1, "cancelled")], "转换表硬约束 · 非法流转 409"),
    ]
    for idx, (title, states, branches, note) in enumerate(cards):
        r, c = idx % 2, idx // 2
        state_card_boxes_edges(colx[r], rows[c], cw, ch, title, states, branches, note, boxes, edges)
    edges.append(Edge([(1115, 770), (1115, 780)], dashed=True, label="确认后转换为任务（幂等）",
                      label_pos=(1115, 748)))
    write_diagram("fig3-3-business-state", w, h, boxes, edges,
                  legend=["实线 = 状态迁移", "虚线 = 失败分支 / 跨对象业务关联"])


# ===================== FIG 3-4 deployment (DB isolated from AI clients) =====================
def fig34():
    w, h = 1600, 860
    boxes = [
        Box(40, 40, 320, 86, ["用户终端", "浏览器"], F_FRONT, bold_title=True),
        Box(40, 156, 320, 90, ["Vue 前端开发服务器", "127.0.0.1:5173 · npm run dev"], F_FRONT, bold_title=True, body_size=16),

        Box(420, 40, 740, 80, ["宿主机 / Docker 开发环境", "docker compose -f docker/compose.dev.yml"], F_LAYER, bold_title=True, body_size=16),
        # FastAPI on the LEFT (tall), AI clients on the RIGHT; DB stays in the left column
        Box(420, 140, 300, 280, ["FastAPI 后端", "127.0.0.1:8000 · 单 uvicorn", "API Router · 认证", "依赖注入"], F_LAYER, bold_title=True, title_size=20, body_size=15),
        Box(800, 150, 260, 60, ["LLM Client"], F_AI, bold_title=True, title_size=18),
        Box(800, 250, 260, 60, ["Embedding Client"], F_AI, bold_title=True, title_size=18),
        Box(800, 350, 260, 60, ["ASR Client"], F_AI, bold_title=True, title_size=18),
        # data stores below FastAPI (left column)
        Box(420, 450, 300, 70, ["PostgreSQL + pgvector", "127.0.0.1:5432 · pgdata 卷"], F_STORE, bold_title=True, title_size=18, body_size=15),
        Box(420, 550, 300, 70, ["本地 storage/", "会议材料 · 音频 · 模板文件"], F_STORE, bold_title=True, title_size=18, body_size=15),
        # local FunASR below ASR client
        Box(800, 460, 260, 70, ["本地 FunASR（可选）", "127.0.0.1:10096 · sensevoice"], F_EXT, bold_title=True, title_size=16, body_size=13),

        Box(1220, 40, 340, 86, ["外部 AI 服务", "（云端，按配置接入）"], F_EXT, bold_title=True),
        Box(1220, 150, 340, 70, ["外部 LLM"], F_EXT),
        Box(1220, 250, 340, 70, ["外部 Embedding"], F_EXT),
        Box(1220, 350, 340, 70, ["外部 ASR"], F_EXT),

        Box(40, 660, 1520, 150, ["规划 / 未实现（生产）",
                                 "Nginx 反向代理 + TLS · 后端多 worker · 前端静态托管",
                                 "监控告警 · 自动备份/恢复演练 · 生产 Compose / 自动部署"], F_PLAN, STROKE_PLAN, dashed=True, bold_title=True, body_size=16),
    ]
    edges = [
        Edge([(200, 126), (200, 156)]),                                              # 浏览器 -> Vue
        Edge([(360, 201), (420, 185)], label="HTTP /api/v1", label_pos=(390, 176)),   # Vue -> FastAPI
        Edge([(720, 180), (800, 180)]),                                              # FastAPI -> LLM Client
        Edge([(720, 280), (800, 280)]),                                              # FastAPI -> Embedding Client
        Edge([(720, 380), (800, 380)]),                                              # FastAPI -> ASR Client
        Edge([(570, 420), (570, 450)], label="SQL", label_pos=(600, 436)),           # FastAPI -> PostgreSQL (left column only)
        Edge([(720, 410), (760, 410), (760, 585), (720, 585)], label="文件读写", label_pos=(775, 500)),  # FastAPI -> storage (right channel x=760)
        Edge([(930, 410), (930, 460)], label="ASR(本地)", label_pos=(1010, 436)),     # ASR Client -> 本地 FunASR
        Edge([(1060, 180), (1220, 185)], label="LLM", label_pos=(1140, 166)),         # LLM Client -> 外部 LLM
        Edge([(1060, 280), (1220, 285)], label="Embedding", label_pos=(1140, 266)),   # Embedding Client -> 外部 Embedding
        Edge([(1060, 380), (1220, 385)], label="ASR", label_pos=(1140, 366)),         # ASR Client -> 外部 ASR
    ]
    write_diagram("fig7-1-deployment", w, h, boxes, edges,
                  legend=["实线 = 当前开发环境实现", "虚线 = 规划项（未实现）"])


# ===================== FIG 4-1 AI data boundary (dashed outbound, solid local) =====================
def fig41():
    w, h = 1560, 880
    boxes = [
        Box(40, 40, 700, 86, ["OpenMIND 本地应用与数据", "前端 · FastAPI 后端 · PostgreSQL+pgvector · storage/"], F_LAYER, bold_title=True, body_size=16),
        Box(860, 40, 660, 86, ["外部 AI 服务（云端）", "数据出网边界 →"], F_EXT, bold_title=True),

        Box(40, 160, 340, 100, ["业务内容", "问题 / 解析文本 / 检索片段", "记录上下文 / 用户记忆 / Prompt"], F_STORE, body_size=15),
        Box(40, 300, 300, 80, ["待向量化文本 / query", "分块文本 · 查询语句"], F_STORE, body_size=16),
        Box(40, 420, 300, 80, ["音频文件", "mp3 / wav / m4a / webm"], F_STORE, body_size=16),
        Box(40, 540, 300, 90, ["本地 FunASR（可选）", "本地处理 · 不发送至外部 ASR"], F_EXT, body_size=16),

        Box(480, 160, 260, 90, ["LLM Client", "/chat/completions"], F_AI, bold_title=True, body_size=16),
        Box(480, 300, 260, 80, ["Embedding Client", "/embeddings（1024 维）"], F_AI, bold_title=True, body_size=16),
        Box(480, 420, 260, 80, ["ASR Client", "/audio/transcriptions"], F_AI, bold_title=True, body_size=16),

        Box(860, 160, 300, 80, ["外部 LLM", "→ 回答（返回本地）"], F_EXT, body_size=16),
        Box(860, 300, 300, 80, ["外部 Embedding", "→ 向量（返回本地）"], F_EXT, body_size=16),
        Box(860, 420, 300, 80, ["外部 ASR", "→ 转写文本（返回本地）"], F_EXT, body_size=16),

        Box(40, 690, 1480, 120, ["BYOK 与数据边界说明",
                                 "LLM：用户 API Key 以密文存储于平台（Fernet），调用时用于访问用户配置的 LLM 服务；Embedding：服务端统一配置，用户不可自备；",
                                 "BYOK 不代表所有 AI 数据均不出本地；云端 LLM/Embedding 与外部 ASR 均存在业务内容出网"], F_PLAN, STROKE, bold_title=False, body_size=14),
    ]
    edges = [
        Edge([(380, 210), (480, 205)], dashed=True, label="LLM（出网）", label_pos=(430, 188), label_size=13),
        Edge([(340, 340), (480, 340)], dashed=True, label="Embedding（出网）", label_pos=(410, 320), label_size=13),
        Edge([(340, 460), (480, 460)], dashed=True, label="ASR（出网）", label_pos=(410, 440), label_size=13),
        Edge([(740, 205), (860, 200)], dashed=True, label="问题/片段", label_pos=(800, 183), label_size=13),
        Edge([(740, 340), (860, 340)], dashed=True, label="待向量化文本", label_pos=(800, 320), label_size=13),
        Edge([(740, 460), (860, 460)], dashed=True, label="音频文件", label_pos=(800, 440), label_size=13),
        Edge([(340, 585), (480, 460)], label="本地转写（不出网）", label_pos=(410, 560), label_size=13),
        Edge([(190, 500), (190, 540)], label="音频", label_pos=(235, 520), label_size=12),
    ]
    write_diagram("fig4-1-ai-data-boundary", w, h, boxes, edges,
                  legend=["实线 = 本地处理（不出网）", "虚线 = 数据出网（云端/外部服务）"])


# ===================== FIG 5-1 audio live chunk transcription =====================
def fig51():
    w, h = 1500, 900
    boxes = [
        Box(60, 40, 360, 64, ["开始实时会话", "POST /audio/live/start → processing"], F_FRONT, body_size=15),
        Box(60, 130, 360, 64, ["上传分片", "live/chunk（seq, offset_seconds）"], F_FRONT, body_size=14),
        Box(60, 220, 360, 64, ["保存分片文件", "audio/{id}/chunks/000N.ext"], F_STORE, body_size=15),
        Box(60, 310, 360, 64, ["逐片 ASR", "TranscriptionClient（外部/本地 FunASR）"], F_AI, body_size=14),
        Box(60, 410, 360, 64, ["追加分段 + 重建全文", "segments[{seq, offset_seconds, text}]"], F_AI, body_size=14),
        Box(60, 510, 360, 64, ["结束：合并分片 + 清理", "live/finish → transcribed / failed"], F_STORE, body_size=14),
        Box(60, 610, 360, 64, ["标记 + 编辑转写", "segments/marker、PATCH /audio/{id}"], F_LAYER, body_size=14),
        Box(60, 710, 360, 64, ["确认 → 生成会议记录", "confirm → RecordType.transcript"], F_FRONT, body_size=14),

        Box(520, 380, 380, 70, ["分片失败：记录 error（不中断）", "segment.error 保留，整体继续处理"], "#FFFFFF", STROKE, dashed=True, body_size=14),
        Box(520, 490, 380, 70, ["分片重试", "POST /audio/{id}/segments/{seq}/retry"], "#FFFFFF", STROKE, dashed=True, body_size=14),

        Box(40, 810, 1420, 60, ["说明：分块上传 + 逐片转写（非 WebSocket/SSE 流式）；已确认音频（有 record_id）不可删除；时间偏移以 offset_seconds 记录。"], "#FFFFFF", STROKE_PLAN, dashed=True, body_size=14),
    ]
    edges = [
        Edge([(240, 104), (240, 130)]),
        Edge([(240, 194), (240, 220)]),
        Edge([(240, 284), (240, 310)]),
        Edge([(240, 374), (240, 410)], label="成功", label_pos=(275, 392), label_size=13),
        Edge([(240, 474), (240, 510)]),
        Edge([(240, 574), (240, 610)]),
        Edge([(240, 674), (240, 710)]),
        Edge([(420, 342), (520, 415)], dashed=True, label="失败", label_pos=(455, 360), label_size=13),
        Edge([(710, 450), (710, 490)]),
        Edge([(520, 525), (470, 525), (470, 360), (420, 360)], dashed=True),
    ]
    write_diagram("fig5-1-audio-live-flow", w, h, boxes, edges,
                  legend=["实线 = 正常流程", "虚线 = 失败分支 / 分片重试"])


fig31()
fig32()
fig33()
fig34()
fig41()
fig51()

print("\n=== VALIDATION ===")
if _problems:
    for p in _problems:
        print("PROBLEM:", p)
else:
    print("no overflow / overlap / out-of-canvas problems")
print("total problems:", len(_problems))
