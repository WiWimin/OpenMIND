# OpenMIND · AI 会议个人助理

## 1. 项目简介

OpenMIND 是面向**个人参会者**的「AI 会议个人助理」Web 应用，围绕「会前准备 → 会中记录 → 会后纪要 → 个人任务跟进」构建可闭环的个人会议工作流。

服务对象是单个参会人，而非团队协作平台；第一版不做多人实时协作、会议主持、共享空间与组织权限体系。

> **当前进度（务必留意）**：仅完成 **第一阶段基础工程（M00）**——前后端骨架、数据库与迁移、Docker Compose、CI 与协作规范。
> **会议业务、用户认证、AI / RAG / 大模型调用均尚未开发**（见第 14、15 节）。仓库尚未进行首次 Git 提交。

## 2. 项目目标

1. **跑通 MVP 闭环**：创建会议 → 导入资料 → AI 理解与检索 → 会前准备 → 会中记录与问答 → 生成纪要 → 提取行动项 → 个人任务跟进。
2. **闭环判定标准**：一次真实会议从「建会」走到「行动项转为个人任务并被跟进」，全程数据可追溯、状态由后端控制、关键结果经用户确认。
3. **工程目标**：建立人人可复现的开发环境、统一的代码与接口规范，以及可协作、可回归的持续集成流程。
4. **质量底线**：个人数据隔离、原始数据与 AI 结果分离、候选与确认分离、密钥不下发前端。

## 3. 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router |
| 后端 | Python、FastAPI、Pydantic |
| ORM 与迁移 | SQLAlchemy、Alembic |
| 数据库 | PostgreSQL 16、pgvector |
| AI 能力 | 云端 LLM + Embedding API（服务端统一调用，**后续阶段**） |
| 文件存储 | 本地持久化目录（MVP） |
| 开发环境 | Docker Compose |
| 质量保障 | pytest、Vitest、ruff、ESLint、Prettier、GitHub Actions CI |

## 4. 项目目录

```text
OpenMIND/
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── api/             # axios 实例与接口封装
│   │   ├── assets/          # 样式与静态资源
│   │   ├── components/      # 可复用组件
│   │   ├── layouts/         # 页面骨架与导航
│   │   ├── router/          # Vue Router 路由
│   │   ├── stores/          # Pinia 状态
│   │   ├── types/           # 前端类型定义
│   │   ├── utils/           # 工具函数
│   │   └── views/           # 页面级组件
│   ├── tests/               # Vitest 测试
│   ├── Dockerfile
│   └── package.json
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用工厂：CORS、异常处理、路由挂载
│   │   ├── api/             # HTTP 路由与依赖注入
│   │   ├── core/            # 配置、日志、异常
│   │   ├── db/              # 声明式 Base、Engine、Session
│   │   ├── models/          # SQLAlchemy ORM 模型
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── repositories/    # 数据库查询与持久化
│   │   ├── services/        # 业务规则
│   │   ├── ai/              # LLM、Embedding、RAG、Prompt（后续阶段）
│   │   └── utils/           # 通用工具
│   ├── alembic/             # Alembic 迁移
│   ├── tests/               # pytest 测试
│   ├── requirements.txt
│   └── Dockerfile
├── docker/                  # Compose 与环境变量示例（与业务代码分离）
│   ├── compose.dev.yml
│   └── .env.example
├── docs/                    # 需求、架构、API、数据库、开发、测试、模块规划
├── scripts/                 # 开发 / 测试 / 数据库校验脚本
├── storage/                 # 运行时文件持久化（不提交真实会议资料）
├── .github/                 # Issue / PR 模板与 CI
├── .editorconfig
├── .dockerignore
├── .gitattributes
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## 5. 开发环境要求

| 依赖 | 版本要求 | 说明 |
| --- | --- | --- |
| Docker Desktop | 含 Docker Compose v2 | 推荐方式，需确保 Docker 引擎已启动 |
| Python | 3.11+ | 本项目验证于 3.13；`backend/Dockerfile` 使用 `python:3.13-slim` |
| Node.js | 20+ | 本项目验证于 24；`frontend/Dockerfile` 使用 `node:22-bookworm` |
| npm | 随 Node 附带 | 前端依赖管理 |
| Git | 任意近期版本 | 版本控制 |

## 6. 环境变量配置

所有环境变量示例集中在 `docker/.env.example`，本地复制为 `docker/.env`（**已被 `.gitignore` 忽略，禁止提交**）：

```bash
cp docker/.env.example docker/.env          # Windows: copy docker\.env.example docker\.env
```

- Docker Compose 启动时从 `docker/.env` 读取变量做插值；未提供时使用 `docker/compose.dev.yml` 中的默认值。
- 后端以原生方式运行时，`pydantic-settings` 会从 `docker/.env` 读取配置。

关键变量：

| 变量 | 作用 | 示例（占位，非真实值） |
| --- | --- | --- |
| `APP_NAME` / `APP_ENV` | 应用名与运行环境 | `OpenMIND` / `development` |
| `API_V1_PREFIX` | API 版本前缀 | `/api/v1` |
| `SECRET_KEY` | 认证签名密钥 | `change-me`（生产必须替换） |
| `POSTGRES_*` | 数据库连接信息 | `openmind` / `change-me` / `openmind` |
| `DATABASE_URL` | SQLAlchemy 连接串（宿主机视角） | `postgresql+psycopg://…@localhost:5432/openmind` |
| `STORAGE_DIR` / `MAX_UPLOAD_MB` | 文件存储目录与上传大小上限 | `./storage` / `20` |
| `LLM_*` / `EMBEDDING_*` | 大模型与向量模型配置（**后续阶段使用**） | `https://api.example.com/v1` 等 |
| `CORS_ORIGINS` | 允许的前端来源 | `http://localhost:5173` |
| `VITE_API_BASE_URL` | 前端 axios `baseURL` | `http://localhost:8000/api/v1` |
| `VITE_APP_ENV` | 前端展示的环境标识 | `development` |
| `VITE_DEV_PROXY_TARGET` | 开发期 Vite 代理目标（示例中默认注释；容器内由 Compose 注入 `http://backend:8000`） | `http://localhost:8000` |

> **安全约束**：LLM / Embedding 密钥只存在于服务端环境变量，不得硬编码，也不能下发前端；`docker/.env` 永不入库。

## 7. Docker 启动方式

在仓库根目录执行：

```bash
# 1) 准备本地环境变量
cp docker/.env.example docker/.env        # Windows: copy docker\.env.example docker\.env

# 2) 构建并启动全部服务（db / backend / frontend）
docker compose -f docker/compose.dev.yml up --build

# 后台运行（推荐）
docker compose -f docker/compose.dev.yml up -d --build

# 3) 首次启动或数据库结构变更后执行迁移
docker compose -f docker/compose.dev.yml exec backend alembic upgrade head
```

也可使用脚本：`scripts/dev.ps1`（Windows）/ `scripts/dev.sh`（macOS、Linux）。

启动后可运行数据库全链路校验：

```powershell
.\scripts\verify-db.ps1        # Windows
```

```bash
./scripts/verify-db.sh         # macOS / Linux / Git Bash
```

## 8. Docker 停止方式

```bash
# 停止并移除容器（保留数据库命名卷，数据不丢失）
docker compose -f docker/compose.dev.yml down

# 仅停止容器，保留容器对象
docker compose -f docker/compose.dev.yml stop
```

> ⚠️ **`down -v` 会一并删除命名卷（`pgdata` 等），导致数据库与本地数据丢失**。除非明确要重置环境，否则不要使用 `down -v`。

## 9. 查看日志方式

```bash
# 跟踪全部服务
docker compose -f docker/compose.dev.yml logs -f

# 跟踪单个服务：db / backend / frontend
docker compose -f docker/compose.dev.yml logs -f backend
docker compose -f docker/compose.dev.yml logs -f frontend
docker compose -f docker/compose.dev.yml logs -f db

# 仅看最近 100 行
docker compose -f docker/compose.dev.yml logs --tail 100 backend
```

## 10. 前端访问地址

| 服务 | 地址 |
| --- | --- |
| 前端首页 | http://localhost:5173 |

## 11. 后端 Swagger 地址

| 文档 | 地址 |
| --- | --- |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |
| 健康检查 | http://localhost:8000/health |
| 数据库就绪探针 | http://localhost:8000/api/v1/health/db |

> 当前后端仅注册健康检查相关接口；业务接口将在后续阶段按 [`docs/api.md`](docs/api.md) 逐步实现。

## 12. Git 分支规范

| 分支 | 用途 | 来源 | 合并去向 |
| --- | --- | --- | --- |
| `main` | 稳定、可演示版本 | 仅接受来自 `develop` 的合并 | —— |
| `develop` | 日常开发集成分支 | 接受所有 `feature/*`、`fix/*` 的 PR | `main`（集成测试通过后） |
| `feature/*` | 具体功能开发 | 从 `develop` 切出 | `develop` |
| `fix/*` | Bug 修复 | 从 `develop` 切出 | `develop` |

命名示例：`feature/m00-project-scaffold`、`feature/m02-record-capture`、`fix/m02-meeting-list`。

提交信息采用 Conventional Commits：`<type>(<scope>): <subject>`，`type` 取 `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore`，`scope` 建议使用模块号（如 `m00`、`m02`）。详见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 13. PR 开发流程

```text
开发者
  ↓
创建 feature 分支
  ↓
开发
  ↓
本地测试
  ↓
提交
  ↓
Pull Request
  ↓
develop
  ↓
集成测试
  ↓
main
```

1. 从 `develop` 切出 `feature/*` 或 `fix/*` 分支。
2. 开发并在**本地测试**通过：
   - 后端：`cd backend && ruff check . && pytest`
   - 前端：`cd frontend && npm run typecheck && npm run lint && npm run test`
   - 或一键：`scripts/test.ps1`（Windows）/ `scripts/test.sh`
3. `git commit` 提交（Conventional Commits）。
4. 发起 **Pull Request** 合并到 `develop`，按 [PR 模板](.github/pull_request_template.md) 填写修改目的、测试方式与结果、是否影响数据库 / 环境变量 / API。
5. 至少一名成员 Code Review 通过、CI 全绿后合并到 `develop`。
6. 在 `develop` 进行**集成测试**，验证通过后合并到 `main`，作为可演示版本。
7. 涉及数据库结构变更必须附带 Alembic 迁移；涉及环境变量变更必须同步 `docker/.env.example`；涉及接口变更必须同步 [`docs/api.md`](docs/api.md)。

> CI（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）仅做检查，不包含任何自动部署流程。

## 14. 当前已完成的功能

> 以下为**已实现并经本地验证**的内容，全部属于第一阶段基础工程（M00）。

**前端基础工程**
- Vue 3 + TypeScript + Vite 骨架，Pinia 与 Vue Router 已接入。
- 首页展示当前环境标识，并通过「后端连接状态」卡片调用 `GET /api/v1/health/db` 显示连接结果（复用 `/api` 代理，5 秒超时，失败归一化为「未连接」）。
- axios 客户端与统一错误归一化（`ApiError`）。
- Vitest 测试 25 个用例、`typecheck`、`lint` 均通过。

**后端基础工程**
- FastAPI 应用工厂：CORS、统一异常处理、`/api/v1` 路由挂载。
- 接口：`GET /health`、`GET /api/v1/health/db`（数据库联合状态），以及统一错误响应体 `{ status, error_code, message }`。
- `pydantic-settings` 配置加载、结构化日志、SQLAlchemy Engine/Session 与探活。
- pytest 5 个用例、`ruff check` 均通过。

**数据与基础设施**
- PostgreSQL 16 + pgvector 由 Docker Compose 管理；Alembic 迁移 `0001_baseline`、`0002_enable_pgvector` 已可在容器内执行并通过校验。
- `docker/compose.dev.yml` 三服务（`db` / `backend` / `frontend`），含 `db` 健康检查与命名卷持久化。
- `scripts/verify-db.ps1` / `.sh` 数据库全链路校验（5 项，失败即非零退出）。

**协作与规范**
- Git 分支规范、Conventional Commits、PR / Issue 模板、CI 检查工作流、`.editorconfig`、前后端 lint/format 配置。

**明确尚未实现（未开发，不在「已完成」范围）**
- 用户认证与个人工作区（M01）：注册、登录、退出、当前用户。
- 会议管理（M02）：会议列表、创建、详情、编辑、删除、归档。
- 会议资料与解析、AI 基础服务与 RAG、会前准备、会中记录与问答、纪要与行动项、个人任务、未解决问题（M03–M09）。
- 大模型 / Embedding 的实际调用（M00-08 仍在后续阶段）。
- 仓库尚未完成首次 Git 提交。

## 15. 后续开发规划

按 [`docs/module-task-plan.md`](docs/module-task-plan.md) 的模块拆分与 [`docs/requirements.md`](docs/requirements.md) 的功能需求推进（**均为规划，尚未实现**）：

| 阶段 | 模块范围 | 目标交付 |
| --- | --- | --- |
| 第一阶段 | M00、M01、M02 | 能登录、创建会议、查看和编辑会议 |
| 第二阶段 | M03、M04 | 能上传材料、解析文本、调用模型、检索来源 |
| 第三阶段 | M05 | 能生成并保存会前准备结果 |
| 第四阶段 | M06、M07 | 能记录会议、生成纪要、提取候选行动项 |
| 第五阶段 | M08、M09 | 能管理个人任务和未解决问题 |
| 第六阶段 | M10 | 完成端到端测试、部署与演示交付 |

模块总览：M01 用户认证 → M02 会议管理 → M03 资料管理与解析 → M04 AI 基础服务与 RAG → M05 会前准备 → M06 会中记录与 AI 助手 → M07 纪要与行动项 → M08 个人任务 → M09 未解决问题 → M10 测试与交付。

## 分工

- **A**：系统与后端集成（工程骨架、认证、会议 CRUD、任务、数据库、权限、部署）
- **B**：AI 后端（文档解析、LLM、Embedding、RAG、Prompt、纪要 / 行动项提取）
- **C**：前端与用户体验（Vue 页面、状态交互、前端测试）

## 常用命令

| 目标 | 命令 |
| --- | --- |
| 启动全部服务 | `docker compose -f docker/compose.dev.yml up -d --build` |
| 停止服务 | `docker compose -f docker/compose.dev.yml down` |
| 查看日志 | `docker compose -f docker/compose.dev.yml logs -f [服务名]` |
| 数据库迁移 | `docker compose -f docker/compose.dev.yml exec backend alembic upgrade head` |
| 数据库校验 | `scripts/verify-db.ps1`（Windows）/ `scripts/verify-db.sh` |
| 后端 lint | `cd backend && ruff check .` |
| 后端测试 | `cd backend && pytest` |
| 前端类型检查 | `cd frontend && npm run typecheck` |
| 前端 lint | `cd frontend && npm run lint` |
| 前端测试 | `cd frontend && npm run test` |
| 前端构建 | `cd frontend && npm run build` |
| 一键测试 | `scripts/test.ps1`（Windows）/ `scripts/test.sh` |

## 文档

- [需求说明](docs/requirements.md)
- [系统架构](docs/architecture.md)
- [接口契约](docs/api.md)
- [数据库设计](docs/database.md)
- [开发指南](docs/development.md)
- [测试策略](docs/testing.md)
- [模块开发任务规划](docs/module-task-plan.md)
- [贡献指南](CONTRIBUTING.md)

## 开发原则

- 先接口、后并行：数据模型与 API 契约先评审，前后端再并行实现。
- 先闭环、后扩展：每阶段完成真实可用的业务流程，再进入下一阶段。
- 先保证业务正确，再优化 AI：权限、持久化、来源追溯和人工确认是底线。
