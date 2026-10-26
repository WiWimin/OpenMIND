# OpenMIND 集成测试与业务闭环验收报告

> 生成时间：2026-10-26
> 验收基线：`develop` @ `833e50f`（PR #52 合并后）+ 验收分支 `feature/final-acceptance-e2e`。
> 执行范围：最新代码 + 真实 PostgreSQL/pgvector + 真实 LLM/Embedding + 真实浏览器 E2E。
> 结论口径：仅在实际执行并取得证据时标记 PASS；外部能力缺失标记 BLOCKED；未执行标记 SKIPPED。

## 一、环境信息

| 项目 | 值 |
| --- | --- |
| 宿主 | Windows + Docker Desktop |
| 数据库 | PostgreSQL 16 + pgvector 0.8.7，容器 `openmind-db-1` |
| 后端 | Docker 容器 `openmind-backend-1`，`127.0.0.1:8000` |
| 前端 | Docker 容器 `openmind-frontend-1`，`127.0.0.1:5173` |
| 浏览器自动化 | Playwright 1.64 + 系统 Microsoft Edge（Chromium 内核） |
| 迁移 | 开发库已升级到 `0018_meeting_audio (head)` |
| LLM / Embedding | 真实服务；浏览器 E2E 通过 BYOK 接口为用户写入 `docker/.env` 中的真实配置 |
| ASR | 当前 `docker/.env` 尚未配置 `ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL` |

## 二、自动化测试

| 检查 | 结果 |
| --- | --- |
| 后端 `ruff check .` | PASS |
| 后端 `pytest -q` | PASS，287 passed |
| 前端 `npm run typecheck` | PASS |
| 前端 `npm run lint` | PASS |
| 前端 `npm run test -- --run` | PASS，72 files / 361 tests |
| 前端 `npm run build` | PASS |
| 浏览器 E2E `npx playwright test` | PASS，4 tests / 1.2m |

## 三、数据库迁移

- 开发库执行 `alembic upgrade head`，当前版本 `0018_meeting_audio (head)`，无错误。
- 既有验收已在全新临时库验证从 `0001_baseline` 连续升级到 `0018_meeting_audio`。
- 已核验新增表/列：
  - `meeting_audio`
  - `knowledge_documents`
  - `knowledge_chunks`
  - `user_memories`
  - `user_model_configs.llm_purpose_models`
  - `meeting_minutes.template` / `source_material_ids`
  - `meeting_records.marker_type`

## 四、真实 HTTP 闭环（此前验收结果，基线 `833e50f`）

使用隔离账号在真实后端 + 真实 PostgreSQL + 真实模型服务上执行：

| 步骤 | 结果 | 证据 |
| --- | --- | --- |
| 注册 | PASS | HTTP 201 |
| 模型配置读取 | PASS | `llm_source=global`（验收进程临时开启全局回退） |
| 保存记忆 | PASS | 默认模板 `concise` 生效 |
| 创建会议 | PASS | HTTP 201 |
| 上传会议资料 | PASS | `processing_status=processed`，真实 Embedding |
| 生成会前准备 | PASS | `status=draft` |
| 创建带标记记录 | PASS | `marker_type=decision` |
| 会议问答 | PASS | 2 条来源，`insufficient_evidence=false` |
| 生成纪要 | PASS | 未显式传模板，使用记忆默认 `concise`；1 个材料来源 |
| 知识库上传 | PASS | `processing_status=processed` |
| 知识库检索 | PASS | 命中 1 条 |
| 音频上传 | PASS（预期失败路径） | `status=failed`，错误为未配置 ASR |

## 五、浏览器 E2E（本轮新增）

运行命令：

```powershell
cd frontend
$env:E2E_LLM_API_BASE=...        # 从 docker/.env 注入，未在输出中打印
$env:E2E_LLM_API_KEY=...
$env:E2E_LLM_MODEL=...
$env:E2E_EMBEDDING_API_BASE=...
$env:E2E_EMBEDDING_API_KEY=...
$env:E2E_EMBEDDING_MODEL=...
npx playwright test --project=chromium --reporter=line
```

| 用例 | 覆盖内容 | 结果 | 耗时 |
| --- | --- | --- | --- |
| `core-flow.spec.ts` | 注册、建会、资料上传解析、记录保存与重点标记、知识库上传/检索、记忆保存 | PASS | 11.8s |
| `ai-flow.spec.ts` | 真实模型：会前准备、会议问答、纪要生成、行动项确认并转个人任务、问题提取 | PASS | 55.6s |
| `audio-flow.spec.ts` | 音频上传；未配置 ASR 时给出明确失败原因 | PASS（失败路径） | 4.8s |
| `local-workspace.spec.ts` | 浏览器不支持目录访问时的降级提示 | PASS | 4.8s |
| 全套 | 4 个用例串行执行 | PASS | 1.2m |

## 六、本轮发现并修复的问题

| 问题 | 影响 | 修复 |
| --- | --- | --- |
| 前端全局 axios 超时 30s，早于后端 LLM 重试完成 | 慢模型下纪要/准备/问答被前端提前中断，用户看到 `timeout of 30000ms exceeded` | 新增 `LONG_REQUEST_TIMEOUT_MS=240_000`，用于 AI 生成、音频转写、解析/向量化上传；补充 API 单测 |
| `docker/compose.dev.yml` 未把 `ASR_*` 注入后端 | 即使 `.env` 配置 ASR，容器内仍不可用 | 在 backend environment 中补充 `ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL` |

## 七、未执行 / BLOCKED

| 项目 | 状态 | 原因 |
| --- | --- | --- |
| 真实 ASR 转写 | BLOCKED | 当前环境未配置 ASR Key；已覆盖 Mock、未配置失败路径和浏览器失败提示 |
| 本地目录真实读写 | PENDING（人工） | 需在支持 File System Access API 的 Chromium/Edge 中人工验收，步骤见 `docs/test-reports/local-workspace-manual-acceptance.md` |
| 生产部署 | SKIPPED | 本次验收基线为 `develop`，尚未执行 `develop → main` 发布 |
| 实时流式 ASR | SKIPPED | 不在当前产品范围 |

## 八、验收结论

| 维度 | 结论 |
| --- | --- |
| 核心会议闭环（资料、准备、记录、问答、纪要、行动项、任务、问题） | PASS（真实 API + 真实数据库 + 真实 LLM/Embedding + 浏览器 E2E） |
| 记录标记、纪要模板、按用途模型、知识库、记忆中心 | PASS（自动化 + 真实 HTTP + 浏览器 E2E） |
| PostgreSQL 迁移 0013–0018 | PASS |
| 音频导入、未配置失败提示与重试入口 | PASS（浏览器 E2E + API 测试；真实 ASR BLOCKED） |
| 前端构建、组件测试与慢请求超时 | PASS |
| 本地目录授权与真实读写 | PENDING（人工验收清单已提供） |

**结论：核心闭环、AI 链路与浏览器 E2E 达到可演示状态。真实 ASR 转写需在配置服务商后补验；本地目录真实读写需人工验收；两项未完成前不得表述为已通过。**

## 九、复验命令

```powershell
# 后端
cd backend
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest

# 前端
cd frontend
npm run typecheck
npm run lint
npm run test -- --run
npm run build

# 浏览器 E2E（先启动 docker/compose.dev.yml，并按 docs/testing.md 注入模型配置）
cd frontend
npm run test:e2e

# 数据库（示例：全新临时库）
$env:DATABASE_URL='postgresql+psycopg://openmind:change-me@localhost:5432/openmind_acceptance'
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
```
