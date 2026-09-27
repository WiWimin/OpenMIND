# 开发指南

## 一、环境要求

- Docker Desktop（含 Docker Compose）
- Python 3.11+（本项目验证于 3.13；容器镜像使用 `python:3.13-slim`）
- Node.js 20+（本项目验证于 24；容器镜像使用 `node:22-bookworm`）与 npm

## 二、环境变量

环境变量示例统一放在 `docker/.env.example`，本地复制为 `docker/.env`：

```bash
cp docker/.env.example docker/.env          # Windows: copy docker\.env.example docker\.env
```

`docker/.env` 已被 `.gitignore` 忽略，请勿提交。

- Docker Compose 启动时从 `docker/.env` 读取变量做插值；未提供时使用 `docker/compose.dev.yml` 中的默认值。
- 后端以原生方式运行时，pydantic-settings 会从 `backend/../docker/.env`（即 `docker/.env`）读取配置。

## 三、方式 A：Docker Compose（推荐）

在仓库根目录执行：

```bash
docker compose -f docker/compose.dev.yml up --build
```

或使用脚本：`scripts/dev.ps1`（Windows）/ `scripts/dev.sh`（macOS、Linux）。

- 前端：http://localhost:5173
- 后端：http://localhost:8000
- 健康检查：`GET http://localhost:8000/health`
- 数据库就绪：`GET http://localhost:8000/api/v1/health/db`

首次启动数据库后执行迁移：

```bash
docker compose -f docker/compose.dev.yml exec backend alembic upgrade head
```

`0002_enable_pgvector` 会在此步骤启用 pgvector 扩展（镜像只提供二进制，扩展必须在库内启用）。

## 三点五、数据库启动验证

迁移执行完毕后，用脚本一次性校验整条数据库链路：

```powershell
# Windows
.\scripts\verify-db.ps1
```

```bash
# macOS / Linux / Git Bash
./scripts/verify-db.sh
```

脚本依次检查 5 项，任一失败立即以非零退出码结束（可用于 CI）：

| # | 检查 | 期望 |
| --- | --- | --- |
| 1 | `pg_isready` | 容器内数据库接受连接 |
| 2 | pgvector 扩展版本 | `SELECT extversion ... WHERE extname='vector'` 返回非空 |
| 3 | `vector` 类型可用性 | `SELECT '[1,2,3]'::vector` 返回 `[1,2,3]` |
| 4 | Alembic 迁移状态 | `alembic current` 与 `alembic heads` 一致 |
| 5 | 后端数据库健康接口 | `GET /api/v1/health/db` → `200` 且 `"database":"up"` |

第 5 项的期望以当前实际契约为准：`/api/v1/health/db` 成功时返回 `{"status":"ok","database":"up"}`；失败时返回统一错误体 `{"status":"error","error_code":...,"message":...,"retryable":...}`（HTTP 503），该格式由 `docs/api.md` 规定，脚本不做任何假设性改写。

可通过环境变量 `HEALTH_URL` 覆盖健康接口地址。脚本从 `docker/.env` 读取 `POSTGRES_USER` / `POSTGRES_DB`；缺少该文件时直接报错退出。

## 四、方式 B：本地原生运行

### 数据库

```bash
docker compose -f docker/compose.dev.yml up -d db
```

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows（Linux/macOS: source .venv/bin/activate）
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- 交互式 API 文档：http://localhost:8000/docs
- 迁移：`alembic upgrade head`（迁移脚本位于 `backend/alembic/`）

### 前端

```bash
cd frontend
npm install
npm run dev
```

Vite 已将 `/api` 代理到 `http://localhost:8000`，端口固定为 `5173`（`strictPort`，被占用时直接报错而非自动换端口）。需要指向其他后端地址时，在启动前设置 `VITE_DEV_PROXY_TARGET`，例如：

```bash
VITE_DEV_PROXY_TARGET=http://localhost:8001 npm run dev
```

#### 前端环境变量

前端只使用 `VITE_` 前缀的**构建期**变量，由 Vite 注入到浏览器产物；后端不读取这些变量，两者不可混用。

| 变量 | 作用 | 默认值 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | axios `baseURL` | `/api/v1` |
| `VITE_APP_ENV` | 首页展示的当前环境 | 回退到 `import.meta.env.MODE` |

`VITE_APP_ENV` 读取顺序为 `import.meta.env.VITE_APP_ENV ?? import.meta.env.MODE`：`development` / `production` 显示为中文名称，其他自定义值原样显示。配置位置为 `frontend/env.d.ts`（类型声明）、`docker/.env.example`（变量样例）、`docker/compose.dev.yml` 的 `frontend` 服务（仅前端注入，不注入后端）。

#### 首页后端连接状态

首页「后端连接状态」调用 `GET /api/v1/health/db`，复用现有 `/api` 代理，不新增重复端点。该接口检查的是**后端与数据库的联合状态**，不等同于后端进程存活：数据库不可用时这张卡片同样显示「未连接」。请求设置 5 秒超时，网络失败、超时与接口返回非健康都会归一化为「未连接」。

## 五、常用命令

| 目标 | 命令 |
| --- | --- |
| 启动全部服务 | `docker compose -f docker/compose.dev.yml up --build` |
| 停止服务 | `docker compose -f docker/compose.dev.yml down` |
| 数据库迁移 | `cd backend && alembic upgrade head` |
| 数据库启动验证 | `scripts/verify-db.ps1`（Windows）/ `scripts/verify-db.sh` |
| 后端 lint | `cd backend && ruff check .` |
| 后端测试 | `cd backend && pytest` |
| 前端类型检查 | `cd frontend && npm run typecheck` |
| 前端 lint | `cd frontend && npm run lint` |
| 前端测试 | `cd frontend && npm run test` |
| 前端构建 | `cd frontend && npm run build` |
| 一键测试 | `scripts/test.ps1`（Windows）/ `scripts/test.sh` |

## 六、目录职责速查

| 目录 | 职责 |
| --- | --- |
| `frontend/src/api/` | axios 实例与接口封装 |
| `frontend/src/views/` | 页面级组件 |
| `frontend/src/components/` | 可复用组件 |
| `frontend/src/layouts/` | 页面骨架与导航 |
| `frontend/src/stores/` | Pinia 状态 |
| `frontend/src/types/` | 前端类型定义 |
| `backend/app/api/` | HTTP 路由与依赖注入 |
| `backend/app/core/` | 配置、日志、异常 |
| `backend/app/db/` | 声明式基类、Engine 与 Session |
| `backend/app/models/` | SQLAlchemy ORM 模型 |
| `backend/app/schemas/` | Pydantic 请求/响应模型 |
| `backend/app/repositories/` | 数据库查询与持久化 |
| `backend/app/services/` | 业务规则 |
| `backend/app/ai/` | LLM、Embedding、RAG、Prompt |
| `docker/` | Compose 与环境变量示例 |

## 七、Git 协作

### 分支策略

| 分支 | 用途 | 来源 | 合并去向 |
| --- | --- | --- | --- |
| `main` | 稳定、可演示版本 | 仅接受来自 `develop` 的合并 | —— |
| `develop` | 日常开发集成分支 | 接受所有 `feature/*`、`fix/*` 的 PR | `main`（集成测试通过后） |
| `feature/*` | 具体功能开发 | 从 `develop` 切出 | `develop` |
| `fix/*` | Bug 修复 | 从 `develop` 切出 | `develop` |

命名示例：`feature/m00-project-scaffold`、`feature/m02-record-capture`、`fix/m02-meeting-list`。

提交信息采用 Conventional Commits：`<type>(<scope>): <subject>`。

### PR 开发流程

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
4. 发起 **Pull Request** 合并到 `develop`，按 [PR 模板](../.github/pull_request_template.md) 填写修改目的、测试方式与结果、是否影响数据库 / 环境变量 / API。
5. 至少一名成员 Code Review 通过、CI 全绿后合并到 `develop`。
6. 在 `develop` 进行**集成测试**，验证通过后合并到 `main`，作为可演示版本。
7. 涉及数据库结构变更必须附带 Alembic 迁移；涉及环境变量变更必须同步 `docker/.env.example`；涉及接口变更必须同步 [`api.md`](api.md)。

> CI 仅做检查（前端依赖与构建、后端依赖与测试、ruff / eslint），不包含任何自动部署流程。分支保护等仓库设置由维护者在 GitHub 网页端配置。

完整说明见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)，概览见 [`../README.md`](../README.md)。

## 八、故障排查

- **`docker compose` 报连接失败**：确认 Docker Desktop 已启动（`docker info` 能返回 Server 版本）。
- **端口占用**：`5432` / `8000` / `5173` 被占用时，先停止冲突进程或修改端口映射。
- **后端连不上数据库**：确认 `db` 容器 healthy（`docker compose -f docker/compose.dev.yml ps`），并核对 `DATABASE_URL` 主机名（容器内为 `db`，本机为 `localhost`）。
- **迁移报错**：确认工作目录在 `backend/`，且 `docker/.env` 中的 `DATABASE_URL` 正确。
- **变量未生效**：确认 `docker/.env` 存在；`docker compose` 只会自动读取项目目录（`docker/`）下的 `.env`。
