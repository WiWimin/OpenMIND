# 系统架构概览

## 项目定位

OpenMIND 是面向个人参会者的「AI 会议个人助理」，围绕会前准备、会中记录、会后纪要和个人任务跟进构建个人会议工作流。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite |
| 后端 | Python、FastAPI、Pydantic |
| ORM 与迁移 | SQLAlchemy、Alembic |
| 数据库 | PostgreSQL、pgvector |
| AI 能力 | 大模型 API + Embedding + RAG（后续阶段） |
| 文件存储 | 本地持久化目录（MVP） |
| 开发环境 | Docker Compose |

## 分层与边界

```text
浏览器
  │  HTTP / JSON
  ▼
前端层（Vue 3）        只负责展示、收集输入、交互与调用 API
  │  /api/v1
  ▼
后端层（FastAPI）      API 路由、身份认证、业务服务、权限校验
  ├── agent/           意图路由与工作流编排（只编排，不写业务 CRUD）
  ├── services/        业务规则与状态流转
  ├── repositories/    数据库访问
  └── ai/              LLM、Embedding、RAG、Prompt（后续阶段）
  ▼
数据层                 PostgreSQL + pgvector + storage/ 文件目录
```

- 前端不直接访问数据库，不持有模型 API 密钥。
- 后端负责身份、权限、数据持久化与业务规则。
- `agent/` 依赖方向为 `api → agent → services → ai`，只做编排与确认门，不直接写会议 CRUD。
- AI 能力层只生成候选结果、语义检索与内容整理，不自行决定任务的创建、完成或撤销。
- 数据层保存原始输入、AI 生成结果、用户确认结果及其关联关系。

## 后端目录结构

```text
backend/app/
├── main.py             应用工厂：CORS、异常处理、路由挂载
├── worker.py           持久化任务队列 worker（`python -m app.worker`）
├── core/               配置、日志、异常
├── db/                 声明式基类 Base、Engine、Session
├── api/                deps.py 与 v1 路由
├── agent/              意图路由、工作流引擎、工具注册表、确认门
├── models/             SQLAlchemy ORM 模型
├── schemas/            Pydantic 请求/响应模型
├── repositories/       数据库查询与持久化
├── services/           业务规则
├── ai/                 LLM、Embedding、Prompt、RAG、解析与提取
└── utils/              通用工具
```

## 数据流（MVP 主线）

创建会议 → 导入资料 → AI 理解与检索 → 会前准备 → 会中记录与问答 → 生成纪要 → 提取行动项 → 个人任务跟进。

## 本地文件访问

- 本地文件夹只通过浏览器 File System Access API 在用户明确授权后访问；后端不读取用户电脑任意绝对路径。
- 本地工作区是**双向同步**（D-38）：资料/音频下载导出、材料/记录/行动项/问题导入、确认纪要以 Markdown 导出并可本地编辑回写；服务端只提供下载、幂等创建与乐观锁更新（`api.md 1.10`），不参与同步调度。
- 同步基线存浏览器 IndexedDB（按 `userId` 隔离），并在会议根写 `.openmind/manifest.json` 作为可移植镜像；对账是「本地快照 / 远端快照 / 上次基线」三方比对。
- **非破坏式**：覆盖本地、回写远端、删除任何一端都必须用户确认；双端同时修改进冲突保留两侧；一端删除不自动传播到另一端。
- 目录权限由浏览器管理；权限失效、取消选择或写入失败必须显示错误，不能静默成功。权限必须在用户手势内申请，页面加载后无法静默恢复。
- 监听：`FileSystemObserver` 优先、30s 轮询兜底，页面隐藏时暂停；扫描带深度/条目/时长预算，忽略临时文件、缓存与日志。
- 当前只支持 Chromium 系浏览器；不支持的浏览器显示明确提示，不影响其他会议功能。
- 文件名、同名覆盖和部分失败由前端逐文件处理；导入失败不回滚已成功文件。服务端本期不提供软删除/回收站，删除即物理删除，必须二次确认。

## 关键约定

- 个人数据隔离；原始数据与 AI 结果分离；候选与确认分离；业务状态由后端控制。
- 鉴权：登录返回 HS256 JWT，请求携带 `Authorization: Bearer <token>`；MVP 不提供 refresh token（见 `docs/api.md 一/二`）。
- 错误响应统一为 `{ status, error_code, message, retryable, details? }`，见 `docs/api.md 一`。
- AI 能力层（LLM/Embedding/RAG/解析/提取）设计与超时重试、幂等、失败补偿见 `docs/ai-design.md`。
- 数据库结构变更必须附带 Alembic 迁移文件。
- 设计文档的职责与唯一事实来源见 `docs/design-baseline.md`。
