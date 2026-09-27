# AGENTS.md

开发约定与上下文说明，供协作成员与编码助手共同遵循。

## 项目概述

OpenMIND 是「AI 会议个人助理」，MVP 闭环为：创建会议 → 导入资料 → 会前准备 → 会中记录与问答 → 生成纪要 → 提取行动项 → 个人任务跟进。

当前已完成 **第一阶段基础工程（M00）**：前后端骨架、数据库与迁移框架、Docker Compose、CI 与协作规范。**尚未开发**会议业务、认证、AI/RAG/大模型调用。

## 架构分层与边界

- 前端（Vue 3）：只负责展示、收集用户输入、交互与调用 API，不直接访问数据库，不持有模型 API 密钥。
- 后端（FastAPI）：负责身份、权限、数据持久化和业务规则。
- AI 能力层（`backend/app/ai/`）：负责生成候选结果、语义检索和内容整理，不自行决定个人任务的创建、完成或撤销。
- 数据层：PostgreSQL + pgvector + 本地文件目录（`storage/`）。

## 目录职责

- `backend/app/main.py`：应用工厂 `create_app()`，装配 CORS、异常处理与 `/api/v1` 路由。
- `backend/app/core/`：`config.py`（pydantic-settings）、`logging.py`、`exceptions.py`（统一错误体）。
- `backend/app/db/`：`base.py`（声明式 `Base`）、`session.py`（engine/Session/`get_db`/探活）。
- `backend/app/api/`：只处理 HTTP 请求、依赖注入和响应；`deps.py` 提供 `DbSession`。
- `backend/app/models/`：SQLAlchemy ORM 模型，继承 `app.db.base.Base`。
- `backend/app/schemas/`：Pydantic 请求/响应模型，与 ORM 模型分离。
- `backend/app/repositories/`：数据库查询与持久化。
- `backend/app/services/`：业务规则（会议归属校验、行动项转任务、状态流转等）。
- `backend/app/ai/`：LLM、Embedding、RAG、Prompt 与结构化输出，禁止与会议 CRUD 混写。
- `docker/`：`compose.dev.yml` 与 `.env.example`，与业务代码分离；`docker/.env` 为本地变量文件（不提交）。
- `frontend/src/api/client.ts`：axios 实例与统一错误规范化；`router/`、`stores/`、`views/`、`types/` 分层。
- `docs/api.md`：接口契约唯一来源。
- `docs/database.md`：共享数据契约。

## 关键约定

- 个人数据隔离：用户只能访问自己拥有的会议、资料、记录、任务和问题。
- 原始数据与 AI 结果分离：不以 AI 结果覆盖用户原文。
- 候选与确认分离：AI 生成的纪要/行动项必须经用户编辑确认。
- 业务状态由后端控制，前端不能通过直接修改状态字段绕过权限或业务规则。
- LLM/Embedding 密钥仅存在于服务端环境变量，禁止硬编码或下发前端。
- 错误响应统一包含 `status`、`error_code`、`message`；错误码见 `docs/api.md`。
- 涉及数据库结构的改动必须附带 Alembic 迁移文件。

## 常用命令

后端（在 `backend/` 下）：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
ruff check .
pytest
alembic upgrade head
```

前端（在 `frontend/` 下）：

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run test
npm run build
```

全套依赖：

```bash
docker compose -f docker/compose.dev.yml up --build   # 需先启动 Docker Desktop
```

提交前必须通过：后端 `ruff check .` + `pytest`；前端 `npm run typecheck` + `npm run lint` + `npm run test`。

## 分支与协作

- 分支：`main`（稳定、可演示）、`develop`（日常集成分支）、`feature/*`（功能开发）、`fix/*`（缺陷修复）。
- 提交信息采用 Conventional Commits，scope 使用模块号（如 `m00`）。
- 详见 `CONTRIBUTING.md`。

## 联调顺序

认证/健康检查/会议 CRUD → 材料上传与记录 → 模型调用/RAG/会前准备 → 会议问答/纪要/行动项 → 行动项确认/任务/问题 → 异常、权限、部署与端到端测试。
