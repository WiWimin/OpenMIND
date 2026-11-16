# 测试策略

## 测试分层

| 层级 | 范围 | 工具 | 位置 |
| --- | --- | --- | --- |
| 单元测试 | 业务规则、纯函数、解析器 | pytest / vitest | `backend/tests/unit`、`frontend/tests` |
| 接口集成测试 | API 请求、响应与错误结构 | pytest + FastAPI TestClient | `backend/tests/api` |
| 数据库集成测试 | pgvector HNSW 索引、SQL ANN 检索 | pytest + PostgreSQL（`TEST_DATABASE_URL`） | `backend/tests/integration` |
| 端到端测试 | 关键业务闭环、真实浏览器交互 | Playwright（Edge / Chromium） | `frontend/e2e` |

## 命令

后端：

```bash
cd backend
ruff check .
pytest
```

PostgreSQL 集成测试（可选，验证 HNSW 索引与 pgvector 检索路径）：

```bash
cd backend
# 未设置 TEST_DATABASE_URL 时自动跳过；需指向已运行的 PostgreSQL + pgvector
TEST_DATABASE_URL=postgresql+psycopg://openmind:change-me@localhost:5432/openmind \
    pytest tests/integration -q
```

前端：

```bash
cd frontend
npm run typecheck
npm run lint
npm run test
```

一键：`scripts/test.ps1`（Windows）或 `scripts/test.sh`。

浏览器 E2E（需先启动 `docker/compose.dev.yml` 中的 db/backend/frontend）：

```powershell
cd frontend
# 二选一：后端临时启用 ALLOW_GLOBAL_FALLBACK=true，或提供自备模型配置
$env:E2E_LLM_API_BASE='https://...'
$env:E2E_LLM_API_KEY='...'
$env:E2E_LLM_MODEL='...'
$env:E2E_EMBEDDING_API_BASE='https://...'
$env:E2E_EMBEDDING_API_KEY='...'
$env:E2E_EMBEDDING_MODEL='...'

npm run test:e2e
npm run test:e2e:headed   # 观察真实交互
```

说明：

- 默认使用系统 Microsoft Edge；若使用 Playwright 自带 Chromium，先 `npx playwright install chromium`，再设置 `E2E_CHANNEL=bundled`。
- 真实 ASR 配置完成后设置 `E2E_EXPECT_ASR=1`，音频用例会断言转写成功并确认保存为记录；未配置时断言明确的失败原因。
- AI 生成、音频转写、解析/向量化上传的前端超时上限为 240s（`frontend/src/api/timeouts.ts`），避免慢模型被全局 30s 超时误判为失败。
- 本地目录授权依赖系统原生目录选择框，无法由 Playwright 驱动；按 `docs/test-reports/local-workspace-manual-acceptance.md` 人工验收。
- 本地工作区双向同步（D-38）：对账逻辑是纯函数，单测覆盖 `frontend/tests/localSync.reconcile.spec.ts`（15 类判定：新增/修改/双改/删除/远端删除/墓碑/触碰/幂等）；接口契约（下载、`client_op_id` 幂等、乐观锁 409）由 `backend/tests/api/test_sync_contracts.py` 与 `frontend/tests/apiSync.spec.ts` 覆盖；纪要 HTML↔Markdown 由 `frontend/tests/minutesMarkdown.spec.ts` 覆盖。真实目录授权、外部程序改动、浏览器重启与多标签仍需人工验收。
- E2E 会在开发库中创建唯一后缀的临时账号、会议与资料，不删除账号；仅限本地/开发环境运行，禁止指向生产库。
- 本地 FunASR：`scripts/asr.ps1 up` 启动 `--profile asr` 并重建 backend；`scripts/asr.ps1 smoke` 做真实转写冒烟；此模式下设置 `E2E_EXPECT_ASR=1` 运行音频 E2E。
- 推荐 E2E 后端启用 `ALLOW_GLOBAL_FALLBACK=true`，避免每个用例都触发真实 BYOK probe；`prepareModelAccess` 会直接复用全局配置。BYOK 路径由 `model-settings.spec.ts` 单独覆盖（需 `E2E_LLM_*` / `E2E_EMBEDDING_*`）。
- `prepareModelAccess` 对网络异常/超时/限流重试 3 次；仍失败时用例标记为 `BLOCKED`（外部模型服务不可用），明确的 401/403/维度错误仍按失败处理。

## 约定

- 后端测试文件命名 `test_*.py`，与源码模块对应；`tests/__init__.py` 保证可导入 `app`。
- 前端单元/组件测试文件命名 `*.spec.ts`，放在 `frontend/tests/`。
- 浏览器 E2E 文件放在 `frontend/e2e/`，命名 `*.spec.ts`；`npm run test` 只运行 Vitest，不包含 E2E。
- 提交前必须本地通过上述检查；CI（`.github/workflows/ci.yml`）会重复执行。

## 第一阶段覆盖

- 健康检查 `/health` 返回 200。
- OpenAPI 文档可访问。
- 数据库就绪探针 `/api/v1/health/db` 已注册（无数据库时返回 503）。
- 未定义路由返回统一错误结构 `{ status, error_code, message, retryable }`。
- 前端 API 客户端配置校验。

## 模块级验收口径（M01–M09）

| 模块 | 关键验收 |
| --- | --- |
| M01 认证 | 注册/登录/当前用户可用；未登录 `401`；重复 `name` 被拒；不返回密码哈希 |
| M02 会议 | CRUD + 归档；越权 `404`；归档只读；存在已转换任务/任务的会议删除返回 `409` |
| M03 资料 | 上传/详情/删除/重试；同步解析失败落库 `failed` + `parse_error`/`parse_error_code`，保留记录与磁盘文件可重试（D-33）；删除后 RAG 不再命中且记录来源置空 |
| M04 RAG | 跨用户不可检索；无命中返回空来源 + `insufficient_evidence` |
| M05 准备 | 生成草稿（新增记录）；编辑 `version` 递增；失败态正确 |
| M06 记录/问答 | 记录增改查；问答返回 `sources`；证据不足标记正确 |
| M07 纪要/行动项 | 纪要草稿；行动项默认 `pending_confirmation`；未确认不可转任务；重复转换幂等 |
| M08 任务 | 状态流转校验；越权 `404`；取消幂等 |
| M09 问题 | 提取候选；状态流转正确；越权 `404` |
| 异步任务（B3） | `ASYNC_JOBS_ENABLED=true` 时 8 个长任务端点返回 `202 + job`；任务 `pending → running → succeeded/failed`、失败带 `error_code`；超窗 `pending`/超时 `running` 读取时回收为 `JOB_TIMEOUT`；越权 `404`；开关关闭回退同步 `200/201`（`tests/api/test_jobs.py`、`tests/unit/test_task_runner.py`） |
| 流式问答（B2） | SSE 事件顺序 `meta → delta → done`；`include_sources=false` 时 meta.sources 为空；首增量前错误 → JSON 错误体（`chat_stream_error_total` 计数）、首增量后错误 → `event: error` 且无 `done`；证据不足单段拒答；`mode=build` → 422；`SSE_CHAT_ENABLED=false` → 404；越权/未登录 `404/401`（`tests/api/test_chat_stream.py`）；LLM 流式增量/首增量前重试 1 次/401 不重试/超时映射/空流 `MODEL_OUTPUT_INVALID`（`tests/unit/test_llm_stream.py`） |

通用：每个模块须覆盖正常流程、越权访问、非法状态流转与统一错误体。

## AI 质量评估

- 建立固定测试集（会议材料 + 记录样例），评测：解析成功率、检索命中率、行动项/问题提取的精确率与召回率。
- 口径固定：以人工标注为基准，记录评测集版本与指标，随 AI 变更更新（见 `docs/ai-design.md` 十一）。

## 当前覆盖现状

- 后端已有单元测试、API 集成测试与 PostgreSQL 集成测试（`backend/tests/unit`、`backend/tests/api`、`backend/tests/integration`）；单测/API 走 SQLite + Mock AI，`backend/tests/integration` 需 `TEST_DATABASE_URL` 指向 PostgreSQL（未设置自动跳过），覆盖 HNSW 索引存在性、pgvector 检索顺序/阈值/用户隔离与执行计划走索引。完整基线为 `ruff check .` + `pytest`。
- RAG 增量索引覆盖：同用户跨会议/跨文档复用（零重复 Embedding 调用）、跨用户不复用、会议材料↔知识库不跨库复用、指纹变化强制重建、开关可关闭（`backend/tests/unit/test_incremental_index.py`）。
- 前端使用 Vitest 组件/Store/API 测试；覆盖长耗时请求超时、解析上传、AI 链路错误态等。
- 思考过程（推理链）覆盖：reasoning 字段解析与思考开关注入、推理截断、只出推理判空且不重试（`backend/tests/unit/test_llm_reasoning.py`、`test_llm_stream.py`）；SSE `meta.trace` / `reasoning` / `done.reasoning` 与 Agent 消息 `meta` 持久化（`backend/tests/api/test_chat_stream.py`、`test_agent.py`）；前端面板自动折叠/手动展开、思考开关与历史恢复（`frontend/tests/AgentChatReasoning.spec.ts`、`sseReasoning.spec.ts`）。
- 浏览器 E2E（Playwright）覆盖：
  - `core-flow.spec.ts`：注册、建会、资料上传、记录标记、知识库检索、记忆保存；
  - `ai-flow.spec.ts`：会前准备、会议问答、纪要生成、行动项确认转任务、问题提取（真实模型）；
  - `audio-flow.spec.ts`：音频上传与转写成功/未配置失败路径；
  - `local-workspace.spec.ts`：浏览器不支持目录访问时的降级提示。
- 真实模型 smoke 由 `backend/scripts/check_ai.py`、`check_rag.py` 单独执行，不等同于 Mock/API 测试。
- 本地目录授权与真实读写无法自动化，按 `docs/test-reports/local-workspace-manual-acceptance.md` 人工验收；不得把未执行项描述为已通过。
