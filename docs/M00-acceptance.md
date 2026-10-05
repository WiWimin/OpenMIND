# M00 工程基础测试验收记录

- 验收日期：2026-09-28
- 验收范围：第一阶段基础工程（M00）——前后端骨架、数据库与迁移、Docker Compose、CI 配置与环境变量规范
- 验收方式：在本仓库实际执行 lint、测试、构建、容器启动、迁移与 HTTP 联调，结果以命令输出为准

## 执行环境

| 项 | 版本 |
| --- | --- |
| 操作系统 | Windows（win32，PowerShell 5.1） |
| Python | 3.13.3（使用 `backend/.venv`） |
| ruff | 0.16.9 |
| pytest | 9.1.1 |
| Node.js / npm | 24.14.1 / 11.11.0 |
| Vite | 5.4.21（`frontend` 构建时输出） |
| Docker CLI / Compose | 29.4.3 / v5.1.3 |
| Docker Engine | 29.4.3（验收时已运行） |
| 数据库镜像 | `pgvector/pgvector:pg16` |
| pgvector 扩展版本 | 0.8.6 |

## 一、后端检查与测试结果

| 命令 | 结果 | 状态 |
| --- | --- | --- |
| `cd backend && .venv\Scripts\ruff.exe check .` | `All checks passed!`，exit 0 | 本次实际执行并通过 |
| `cd backend && .venv\Scripts\pytest.exe` | `5 passed`（`tests/test_health.py`），exit 0 | 本次实际执行并通过 |

说明：

- 健康检查接口（`GET /health`、`GET /api/v1/health/db`）的 5 个测试用例全部通过。
- pytest 输出 1 条 **库级 deprecation 警告**（非本项目代码）：`StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`，来自 fastapi/starlette 自身依赖，不影响功能，后续升级依赖时处理。
- 后端无需修复任何代码。

## 二、前端检查与测试结果

| 命令 | 结果 | 状态 |
| --- | --- | --- |
| `cd frontend && npm run typecheck` | exit 0 | 本次实际执行并通过 |
| `cd frontend && npm run lint` | exit 0（eslint） | 本次实际执行并通过 |
| `cd frontend && npm run test` | `25 passed`（5 个 spec 文件） | 本次实际执行并通过 |
| `cd frontend && npm run build` | exit 0（vite 构建 94 modules） | 本次实际执行并通过 |

测试用例分布：`environment.spec.ts` 3、`health.spec.ts` 5、`InfoCard.spec.ts` 7、`HomeView.spec.ts` 8、`client.spec.ts` 2，合计 25，与 `README.md` 第 14 节声明一致。

## 三、数据库、pgvector 与 Alembic 迁移验证

| 命令 / 检查 | 结果 | 状态 |
| --- | --- | --- |
| `docker compose -f docker/compose.dev.yml up -d --build` | exit 0；`db` healthy，`backend` / `frontend` 均 Up | 本次实际执行并通过 |
| `docker compose ... exec backend alembic upgrade head` | exit 0 | 本次实际执行并通过 |
| `alembic current` / `alembic heads` | 均为 `0002_enable_pgvector (head)` | 本次实际执行并通过 |
| `scripts\verify-db.ps1`（5 项全链路校验） | 5/5 通过，exit 0 | 本次实际执行并通过 |

`verify-db.ps1` 逐项结果：

1. PostgreSQL 就绪：`/var/run/postgresql:5432 - accepting connections`
2. pgvector 扩展版本：`0.8.6`
3. `vector` 类型可用：`SELECT '[1,2,3]'::vector` 返回 `[1,2,3]`
4. Alembic 迁移状态：head 与 current 一致（`0002_enable_pgvector`）
5. 后端数据库健康接口：`GET http://localhost:8000/api/v1/health/db` → HTTP 200，body `{"status":"ok","database":"up"}`

## 四、前后端 HTTP 联调

| 检查 | 结果 | 状态 |
| --- | --- | --- |
| `GET http://localhost:5173/`（前端首页） | HTTP 200，返回 OpenMIND 页面 HTML | 本次实际执行并通过 |
| `GET http://localhost:5173/api/v1/health/db`（前端 `/api` 代理链路） | HTTP 200，body `{"status":"ok","database":"up"}` | 本次实际执行并通过 |
| `GET http://localhost:8000/api/v1/health/db`（后端直连） | HTTP 200，body `{"status":"ok","database":"up"}` | 本次实际执行并通过 |

说明：

- 前端 axios `baseURL` 为 `import.meta.env.VITE_API_BASE_URL ?? '/api/v1'`，首页 `HomeView.vue` 经 `api/health.ts` 调用 `/health/db`，联调验证了该完整链路。
- 首页「已连接」展示逻辑由 `HomeView.spec.ts` / `health.spec.ts` 覆盖；**未进行浏览器自动化或可视化（截图/人工目视）验收**，页面渲染最终态不在本次验收范围。

## 五、README 文档修正

本次仅修正过期且与事实不符的说明（基于当前仓库提交与分支状态），修改文件 `README.md`，变更摘要 `1 insertion(+), 2 deletions(-)`：

| 位置 | 修改前 | 修改后 |
| --- | --- | --- |
| 第 10 行 | 尾句「仓库尚未进行首次 Git 提交。」 | 删除该句 |
| 第 272 行（原） | 列表项「仓库尚未完成首次 Git 提交。」 | 删除整条 |

核对后确认为准确、未改动的 README 内容：第 14 节的测试用例数量（前端 25 / 后端 5）、迁移与 pgvector 校验声明（本次实测一致）；目录结构（第 4 节）、分支规范（第 12 节）、启动步骤（第 7 节）均与仓库实际一致。

## 六、任务状态变化（`docs/module-task-plan.md`）

| 编号 | 原状态 | 新状态 | 依据 |
| --- | --- | --- | --- |
| M00-01 | 进行中 | 已完成 | 仓库已创建（`origin` 指向 GitHub），`main` / `develop` 均已推送远端，存在提交 `61b5b61` |
| M00-08 | 后续阶段 | 未完成（B 负责，后续阶段） | `app/ai/llm`、`app/ai/embeddings` 仍为空包，未配置真实 `LLM_*` / `EMBEDDING_*`，未做连通性验证 |

M00-02、M00-03、M00-04、M00-05、M00-06、M00-07、M00-09 原即为「已完成」，本次核对后保持：

- M00-02：PR / Issue 模板与分支规范已配置（`.github/`、`CONTRIBUTING.md`、`README` 第 12–13 节）。
- M00-03：Vue 3 + TypeScript + Vite 可启动、构建通过（本次前端验收通过）。
- M00-04：FastAPI 可启动并返回健康状态（本次后端与联调验收通过）。
- M00-05：PostgreSQL + pgvector 容器启动、后端可连接（本次 `verify-db` 第 5 项验证通过）。
- M00-06：SQLAlchemy / Alembic / Pydantic 配置齐备，初始迁移可执行（本次验证 current == head）。
- M00-07：环境变量集中在 `docker/.env.example`，`docker/.env` 被 `.gitignore` 忽略（`git check-ignore` 确认），仓库未跟踪任何真实密钥。
- M00-09：`README.md` 与 `docs/development.md`、`scripts/` 启动文档齐备，本次按文档启动与校验均成功。

## 七、未完成事项与未验证项（含已确认事项）

| 项 | 归属 | 状态 | 说明 |
| --- | --- | --- | --- |
| M00-08：验证模型 API 与 Embedding API 连通性 | B | 后续待完成 | 需在开发机 `docker/.env` 配置真实端点与密钥（不入库），补充连通性自检后再验收 |
| 首页健康状态可视化验收 | — | 未验证 | 未执行浏览器自动化/截图，展示逻辑仅由单元测试覆盖 |
| GitHub 分支保护配置 | A（人工） | 未验证 | 需在 GitHub 网页端配置，仓库内无对应文件 |
| GitHub Actions CI 实跑 | 全员 | 本次实际执行并通过 | GitHub Actions 已在提交 `61b5b61` 上实际运行并通过（main 分支 run #1、develop 分支 run #2，二者结论均为 `success`），检查上下文为 `Backend (ruff + pytest)` 与 `Frontend (typecheck + lint + test + build)`；经 GitHub 公开 REST API 只读查询核实 |

需要人工处理的问题：

- `docs/module-task-plan.md` 中 M01 及以后各模块仍为规划状态，不属于 M00 验收范围，无需处理。
- pytest 库级 deprecation 警告（fastapi/starlette TestClient）为依赖升级事项，建议随依赖升级统一处理。

## 八、验收结论

M00 中除 M00-08 外均已完成并完成实际验证（详见上文各表）；M00-08 由 B 负责，在配置模型 / Embedding 密钥后另行验收。全部命令与结果真实执行，未伪造或跳过的测试均如实标注。GitHub Actions CI 已在远端（main、develop 两分支）实际运行并通过，相关证据见第七节。
