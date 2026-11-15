# OpenMIND 技术文档大纲（对照传智杯 AI Web 赛道评分表）

> 用途：参赛技术文档（PDF，≤30 页）写作大纲。每章标注对应评分项与分值、必须覆盖的要点、代码/文档证据出处，以及录制/写作前待补素材。
> 评分依据：2026 第九届传智杯 AI WEB 网页开发挑战赛公开评审细则（AI 技术深度 35%、创新性 25%、前端工程质量 10%、实用性 10%、用户体验 10%、社会价值与商业潜力 10%）。
> 事实纪律：只写仓库内已实现能力；规划项明确标注「后续演进」；未实现能力不写成现状。

## 提交物清单（先于正文核对）

| 要求项 | 现状 | 待办 |
| --- | --- | --- |
| 代码仓库（GitHub/Gitee 公开或提供评审权限） | 仓库含前后端、`docker/.env.example`、依赖清单、docs | 确认仓库公开可访问、Git 提交历史完整 |
| README（介绍/架构/运行指南/团队信息） | 已有 `README.md` | 补团队成员、学号、指导教师信息 |
| 演示视频（5–8 分钟、1080p MP4、普通话字幕） | 字幕稿见 `docs/competition-demo-script.md` | 录制并导出 MP4 |
| 技术文档 PDF（≤30 页） | 本大纲为骨架 | 按章扩写并导出 PDF |
| 在线演示（可选加分） | 本地 `compose.dev.yml`；仓库无自动部署流水线 | 评审前准备公网地址 + 测试账号，确认评审期可用 |
| 密钥合规 | BYOK Fernet 加密、掩码返回、env 模板 | 提交前确认公开仓库无真实密钥 |

---

## 第 0 章 封面与摘要（1 页）

- 项目名称、一句话定位：面向个人参会者的 AI 会议个人助理。
- 团队成员、学号、班级、指导教师。
- 摘要（200 字内）：场景、技术栈、核心 AI 能力、闭环结果。
- 目录与版本日期。

## 第 1 章 项目概述与需求分析（对应 实用性 10% · 场景真实性 5%）

### 1.1 选题背景
- 个人参会者在会前资料准备、会中记录、会后纪要与行动项跟进上的痛点。
- 与团队协作型会议平台的边界：本项目服务单个参会人，第一版不做多人实时协作、会议主持、共享空间与组织权限。
- 证据：`README.md` §1、`docs/requirements.md`。

### 1.2 用户画像与核心场景
- 典型用户：参会学生/职场个人；主流程：建会 → 传资料 → 会前准备 → 会中转写与问答 → 纪要 → 行动项 → 个人任务跟进。
- 场景真实性论证：每一步对应可操作的页面与后端接口，而非概念演示。

### 1.3 需求范围与明确不做项
- 已实现 MVP 闭环 M00–M10 及扩展能力（BYOK、用途模型路由、个人知识库、记忆中心、会议模板、本地工作区、音频转写）。
- 第一版不做：多人协作、会议主持、移动端、多语言、自动化部署流水线；扫描件 OCR、rerank、转写记录入库检索等见「不足与演进」。
- 证据：`docs/requirements.md`、`README.md` §14「尚未实现」。

## 第 2 章 系统架构设计（对应 前端工程质量 10% 基础、AI 深度承载框架）

### 2.1 技术栈
- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router。
- 后端：Python、FastAPI、Pydantic、SQLAlchemy、Alembic。
- 数据：PostgreSQL 16、pgvector；文件存储本地目录 `storage/`。
- AI：OpenAI 兼容 LLM（BYOK）、服务端统一 Embedding、RAG Judge、OpenAI 兼容/本地 FunASR 语音转写。
- 证据：`README.md` §3、`docs/architecture.md`。

### 2.2 分层与边界
- 浏览器 → 前端 SPA（仅展示/交互/调 API，不直连数据库、不持密钥）→ FastAPI `/api/v1`（鉴权、依赖注入、统一错误体）→ `services/`（业务规则与隔离）→ `ai/`（只产候选，不决定业务状态）→ PostgreSQL/pgvector + `storage/`。
- 依赖方向：`api → agent → services → ai`；`agent/` 只编排与确认门，不写会议 CRUD。
- 配一张分层架构图（可沿用演示架构图，分层名称与代码目录对齐）。
- 证据：`docs/architecture.md`「分层与边界」、`backend/app/` 目录。

### 2.3 关键数据流（MVP 主线）
- 创建会议 → 导入资料 → 解析分块向量化 → 会前准备 → 会中记录/问答 → 纪要 → 行动项 → 个人任务。
- 标注每条数据的原始态、AI 候选态、用户确认态三者分离。

## 第 3 章 AI 技术方案（对应 AI 技术深度 35%，全文重点）

> 本章是最高权重章节，按六个考察点分节，每节写「选型理由 → 集成方式 → 关键实现 → 优化/兜底」。

### 3.1 大模型集成质量（8%）
- 接入方式：OpenAI 兼容 `/chat/completions`；BYOK 用户自备 `api_base/key/model`，服务端全局仅在显式开关下回退。
- 用途级模型路由：按 purpose 覆盖模型名；请求级模型覆盖。
- 结构化输出管线：解析预处理 → schema + 业务字段校验 → 1 次修复重试 → 统一报错/降级与规范日志。
- 消息序列构造：问答与交付物 Prompt 按 `system → 对话历史 → 当前 user` 拼装；历史由服务端按会话取数，带条数（6）与字符（3000）双上限，前端不回传历史。
- 超时/重试/兜底：传输重试在 `ai/retry.py`，结构化修复在 `ai/structured.py`，业务步骤重试在工作流层，三层职责不重叠。
- 证据：`backend/app/ai/llm/client.py`、`services/model_config_service.py`、`docs/ai-design.md`。

### 3.2 Agent / 工作流设计（8%）
- 自研声明式引擎：`Step`（工具 + 状态输入 + 重试策略 + 失败策略）、`Edge`（条件分支）、`WorkflowRunner`；未引入 LangGraph。
- 意图路由优先级：显式意图 → 规则正则（置信度阈值）→ LLM 兜底 → 默认对话；工具由后端注册表提供，不由大模型自选。
- 两条执行通道：轻量单步 `quick_task`；只读检索生成 `pipeline/brief`；有副作用/确认门/多步重试走 `workflow`。
- 已登记工作流：`web_fallback`（无证据 → 确认 → 批准才联网）、`transcribe_to_minutes`（转写 → 确认门 → 纪要草稿 → 可选行动项）。
- 可控性：确认门 `WaitForConfirmation` 落 `agent_pending_actions`；步数上限 `max_steps`、时长上限 `max_wall_s` 熔断；状态与当前步骤落库快照；支持取消运行。
- 证据：`backend/app/agent/workflow.py`、`intent.py`、`workflows.py`、`service.py`、`tools.py`、`docs/agent-framework.md`。

### 3.3 RAG 技术应用（6%）
- 双链路隔离：会议材料 `DocumentChunk → MeetingMaterial → Meeting.user_id`；个人知识库 `KnowledgeChunk → KnowledgeDocument.user_id`；权限在 SQL 前置过滤。
- 检索策略：Top-K（默认 top5）+ 相似度阈值（min_score 0.3）；pgvector HNSW 近邻（`auto` 分流，应用层余弦可回滚）；ANN 过采样补偿过滤召回。
- 低分带 Judge：top1 低于 `rag_judge_min_score`（0.6）时复核 top3；判无关整体拒答；Judge 不可用回退分数判定，不阻断检索。
- 写入侧：解析 → 句子边界分块（800 字符 / 120 重叠）→ 1024 维向量化 → 入库；增量索引按 `content_hash` + 索引指纹复用分块，零重复 Embedding 消耗。
- 评测素材：RAG 评测报告（负样本拦截率、会议材料 hit@5），引用 `docs/test-reports/rag-eval-report.md` 原始数字，不自行改写。
- 证据：`backend/app/ai/rag/retriever.py`、`relevance.py`、`indexing/chunker.py`、`fingerprint.py`、`services/indexing_service.py`、`material_service.py`。

### 3.4 多模态能力（5%）
- 现状如实写：当前多模态仅覆盖**语音转写（ASR）**，支持外部 OpenAI 兼容 ASR 或本地 FunASR（SenseVoice）；webm/ogg 经 ffmpeg 转码 wav 后送转写。
- 明确边界：未接入图像、视频、视觉大模型；不要在文档中扩展承诺。
- 证据：`docker/.env.example` ASR 段、`backend/app/api/v1/audio.py`、`docs/development.md` ASR 段。

### 3.5 AI 安全与可控性（4%）
- 候选与确认分离：纪要/行动项/转写须用户确认后才落业务状态；AI 结果不覆盖原始记录。
- 提示词注入防护：外部模板与用户补充只注入 user 消息段，system 置中立防御句；用户画像注入 ≤500 字符截断；对话历史只作参考数据、不作为指令，其中出现的要求/命令/角色设定不执行，指代按历史理解但结论必须由资料支撑。
- 兜底与可追溯：无证据明确拒答，完全无证据才两段式联网补救并标注来源；日志只记 verdict/score，不记查询原文与模型原文。
- 密钥安全：服务端存储、Fernet 加密、掩码返回、禁止硬编码；`docker/.env` 不入库。
- 证据：`docs/ai-design.md`、`services/memory_service.py`、`core/crypto.py`、`agent/tools.py`。

### 3.6 MCP / 工具集成（4%）
- 现状如实写：采用**自研工具注册表 + Function Calling 式调用**（`tool_functions` 登记工具名、入参、是否需确认），未接入 MCP 协议。
- 工具分类：只读检索/生成类、有副作用类（需确认门）；联网前请求用户确认。
- 答辩口径：若被问 MCP，说明当前为自研注册表，协议化接入列入演进方向。
- 证据：`backend/app/agent/tools.py`、`service.py`。

## 第 4 章 核心功能实现（对应 实用性 10% · 方案有效性 5%）

### 4.1 会前：资料管理与准备
- 材料上传解析（PDF/DOCX/TXT）、会前准备生成、模板注入。
### 4.2 会中：记录与问答
- 会议记录、重点/决议/疑问标记；问答检索 + 来源标注；最近有限条记录上下文（最近 20 条中按问题相关性筛选，取相关 top5、合计 ≤4000 字符）。
- 多轮对话历史：Agent 会话问答由服务端按 `session_id` 提供历史，前端不回传消息；默认注入最近 6 条、≤3000 字符的已完成 user/assistant 消息，`include_history` 可关闭；确认门提示、失败消息与当前轮不注入。普通会议问答接口（`/meetings/{id}/chat`、`/chat/stream`）当前仍为单轮，不带历史。
- 能力边界：转写与会议记录不进入向量库；完整历史检索为后续项。
### 4.3 会后：纪要与行动项
- 纪要草稿生成、富文本编辑、DOCX 导出、模板；行动项候选 → 用户确认 → 个人任务。
### 4.4 记忆中心与个人知识库
- 实体偏好记忆字段与注入规则；个人知识库独立隔离检索。
### 4.5 本地会议工作区同步
- 浏览器 File System Access API 授权扫描；本地快照/远端快照/基线三方对账；大小/mtime/哈希增量判定；乐观锁（`expected_updated_at`/`version`）+ 幂等键 `client_op_id`。
- 非破坏式：拉取自动增量；回写、删除、冲突保留两侧，均需用户确认；基线存 IndexedDB，目录写 `.openmind/manifest.json` 镜像。
- 证据：`frontend/src/services/localSync/`、`backend/app/services/sync_support.py`、`docs/architecture.md`「本地文件访问」。
### 4.6 个人任务管理
- 行动项转任务；状态 todo/in_progress/done/archived；筛选、更新、撤回、取消。
- 与 Agent 运行观测的边界：任务页为个人业务任务；Agent 轨迹在对话/转写流程内，由 runs/steps/pending-actions 接口提供。

## 第 5 章 前端工程与用户体验（对应 前端工程质量 10% + 用户体验 10%）

### 5.1 前端代码质量（4%）
- TypeScript 规范、目录分层（api/components/composables/stores/views/types/utils）、统一 axios 错误归一化。
- 质量命令：`typecheck`、`lint`、`test`（Vitest）、`build`；后端 `ruff`、`pytest`。
- 待补素材：最新测试用例数、文件数以仓库 `npm run test` / `pytest` 实际输出为准，不在文档写死旧数字。

### 5.2 组件化与架构设计（3%）
- 页面外壳 `WorkspaceLayout`、导航按一级归属渲染二级菜单、可复用组件与组合式函数；Pinia 服务端状态与本地状态分离。
- 证据：`frontend/src/layouts/`、`stores/`、`composables/`、`constants/navigation.ts`。

### 5.3 前端性能优化（3%）
- 已落实：列表分页加载、异步列表组合式封装、空态/加载/错误边界。
- 待核实后再写：路由懒加载、代码分割、资源/缓存策略——写作前在 `router/`、`vite.config` 中确认现状，未做的不列入已实现。

### 5.4 UI 设计与视觉表现（4%）
- 设计系统：单一主色蓝、浅灰背景、白色轻卡片、淡边框、克制留白；选中态浅蓝底 + 左蓝条；响应式卡片列数回落。
- 待补素材：关键页面截图（主页、会议工作台、任务管理、转写、纪要）。

### 5.5 交互体验（3%）
- 路由切换、加载状态、操作反馈、重试入口、空态引导；首次登录引导序列（记忆中心 → 本地文件夹配置）。

### 5.6 AI 交互体验（3%）
- SSE 流式文本渲染、思考/增量状态、错误边界与拒答文案；确认门弹窗与待确认操作列表。

## 第 6 章 数据与权限设计（支撑 安全可控 + 实用性）

- 主要数据表：用户、会议、材料、分块/知识分块、记录、纪要、行动项、任务、问题、用户记忆、模型配置、音频/转写、Agent 会话/消息/运行/步骤/待确认动作、异步任务。
- 隔离规则：所有业务查询按 `user_id` 前置过滤；服务层 `get_owned_*` 二次归属校验。
- 状态由后端控制：前端不能绕过接口改状态；原始数据与 AI 结果分离。
- 证据：`docs/database.md`、`backend/app/models/`、`api/deps.py`、各 `services/*_service.py`。

## 第 7 章 测试与质量保障（支撑 工程质量 + 方案有效性）

- 后端：pytest 用例、ruff 静态检查；结构化输出与 RAG 关键路径测试。
- 前端：Vitest 组件/组合式函数测试；Playwright E2E 覆盖核心闭环（需模型配置的用例无凭据时跳过）。
- 评测：RAG 检索评测报告；ASR 本地 FunASR 真实转写与浏览器 E2E 记录。
- 待补素材：最新测试运行截图/输出、评测结论引用路径。

## 第 8 章 部署与运行环境（对应 在线演示加分项）

- 本地/容器部署：`docker compose -f docker/compose.dev.yml up --build`；迁移 `alembic upgrade head`；索引重建脚本。
- 环境变量：集中 `docker/.env.example`，密钥不入库；前端代理与后端地址配置。
- 演示环境安排：学生机高端口对外、评审期保活、评审测试账号——属部署准备项，文档中与代码实现分开陈述。
- 证据：`README.md` §5–§10、`docs/development.md`、`docker/compose.dev.yml`、`docker/.env.example`。

## 第 9 章 创新点与社会价值、商业潜力（对应 创新性 25% + 社会价值商业潜力 10%）

### 9.1 选题创新（10%）
- 面向个人参会者的全流程闭环，而非单点问答；把会前准备、会中记录、会后纪要、任务跟进串成可追溯链路。

### 9.2 技术方案创新（8%）
- 公共调度底座 + 差异化 Workflow：轻量单步与复杂多步分流；确认门、重试、预算熔断、状态快照的可控编排。
- 三层记忆 + RAG 组合：实体偏好、会话留存、向量语义分层；低分带 Judge 减少负样本干扰。
- 本地工作区三方对账同步：基线 + 哈希增量 + 乐观锁/幂等，非破坏式回写。

### 9.3 交互模式创新（7%）
- AI 候选 → 人工确认门的可控交互；流式回答与待确认操作可视化；首次引导降低使用门槛。

### 9.4 社会价值（5%）
- 降低个人参会者整理会议记录的负担；辅助行动项落地与跟进；隐私优先：个人数据隔离、密钥不下发、原始记录不被 AI 覆盖。

### 9.5 商业潜力（5%）
- 可延展方向：团队版协作、更多模板与行业场景、更多 ASR/模型接入；当前为个人 MVP，商业论述标注为设想而非现状。

## 第 10 章 不足与演进路线（对应 答辩可信度，避免夸大）

- 现状不足：
  - 多轮历史仅有最近有限轮预算（6 条/3000 字符），且只在 Agent 会话问答链路注入；普通会议问答接口仍为单轮，长程指代与跨会议上下文能力有限；
  - 会议记录不入向量库，问答仅附最近有限条上下文；
  - 多模态仅语音；工具集成未走 MCP 协议；
  - 向量模型服务端统一配置，用户不可自备切换；
  - 本地同步回写/删除需人工确认；无自动化部署流水线。
- 演进计划：放宽历史预算并把历史注入扩展到普通问答链路，完善跨会议会话记忆与多轮追问；轻量任务链路优化；rerank 与更多检索策略；MCP 协议化接入；图像/视频模态扩展。
- 证据：`README.md` §14、`docs/requirements.md` 不做范围、本项目核查结论。

## 附录

- A. 接口索引：对应 `docs/api.md`。
- B. 数据模型索引：对应 `docs/database.md`。
- C. 环境变量与配置索引：对应 `docker/.env.example`、`docs/development.md`。
- D. 测试与评测报告索引：`docs/testing.md`、`docs/test-reports/`。
- E. 团队信息与提交物清单（视频链接、仓库地址、演示账号说明）。

---

## 篇幅与写作检查清单

- [ ] 全文 ≤30 页；AI 技术方案章（第 3 章）占比不低于全文 1/3。
- [ ] 每个 AI 结论都能指到具体代码或文档路径；评测数字标注报告出处。
- [ ] 已实现 / 规划项 / 未实现三类措辞分清；未出现 MD5、WebSocket 音频、全自动双向同步、向量模型用户切换等与代码不符的表述；历史口径与代码一致（Agent 会话默认注入最近 6 条/≤3000 字符、可关闭，普通问答单轮），不写成「历史完全不进推理」或「全量历史连续对话」。
- [ ] 公开仓库无真实密钥；截图无第三方水印与敏感信息。
- [ ] README、视频、PDF、演示地址四项提交物齐全后再统一提交。
