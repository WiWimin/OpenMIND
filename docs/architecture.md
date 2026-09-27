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
  ├── services/        业务规则与状态流转
  ├── repositories/    数据库访问
  └── ai/              LLM、Embedding、RAG、Prompt（后续阶段）
  ▼
数据层                 PostgreSQL + pgvector + storage/ 文件目录
```

- 前端不直接访问数据库，不持有模型 API 密钥。
- 后端负责身份、权限、数据持久化与业务规则。
- AI 能力层只生成候选结果、语义检索与内容整理，不自行决定任务的创建、完成或撤销。
- 数据层保存原始输入、AI 生成结果、用户确认结果及其关联关系。

## 后端目录结构

```text
backend/app/
├── main.py             应用工厂：CORS、异常处理、路由挂载
├── core/               配置、日志、异常
├── db/                 声明式基类 Base、Engine、Session
├── api/                deps.py 与 v1 路由
├── models/             SQLAlchemy ORM 模型
├── schemas/            Pydantic 请求/响应模型
├── repositories/       数据库查询与持久化
├── services/           业务规则
├── ai/                 LLM、Embedding、Prompt、RAG、解析与提取
└── utils/              通用工具
```

## 数据流（MVP 主线）

创建会议 → 导入资料 → AI 理解与检索 → 会前准备 → 会中记录与问答 → 生成纪要 → 提取行动项 → 个人任务跟进。

## 关键约定

- 个人数据隔离；原始数据与 AI 结果分离；候选与确认分离；业务状态由后端控制。
- 错误响应统一为 `{ status, error_code, message }`，见 `docs/api.md`。
- 数据库结构变更必须附带 Alembic 迁移文件。
