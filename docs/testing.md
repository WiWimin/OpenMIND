# 测试策略

## 测试分层

| 层级 | 范围 | 工具 | 位置 |
| --- | --- | --- | --- |
| 单元测试 | 业务规则、纯函数、解析器 | pytest / vitest | `backend/tests/unit`、`frontend/tests` |
| 接口集成测试 | API 请求、响应与错误结构 | pytest + FastAPI TestClient | `backend/tests/api` |
| 端到端测试 | 关键业务闭环、真实浏览器交互 | Playwright（Edge / Chromium） | `frontend/e2e` |

## 命令

后端：

```bash
cd backend
ruff check .
pytest
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
| M03 资料 | 上传/详情/删除；同步解析失败以 `failed` + `parse_error` 表达；删除后 RAG 不再命中且记录来源置空 |
| M04 RAG | 跨用户不可检索；无命中返回空来源 + `insufficient_evidence` |
| M05 准备 | 生成草稿（新增记录）；编辑 `version` 递增；失败态正确 |
| M06 记录/问答 | 记录增改查；问答返回 `sources`；证据不足标记正确 |
| M07 纪要/行动项 | 纪要草稿；行动项默认 `pending_confirmation`；未确认不可转任务；重复转换幂等 |
| M08 任务 | 状态流转校验；越权 `404`；取消幂等 |
| M09 问题 | 提取候选；状态流转正确；越权 `404` |

通用：每个模块须覆盖正常流程、越权访问、非法状态流转与统一错误体。

## AI 质量评估

- 建立固定测试集（会议材料 + 记录样例），评测：解析成功率、检索命中率、行动项/问题提取的精确率与召回率。
- 口径固定：以人工标注为基准，记录评测集版本与指标，随 AI 变更更新（见 `docs/ai-design.md` 十一）。

## 当前覆盖现状

- 后端已有单元测试与 API 集成测试（`backend/tests/unit`、`backend/tests/api`），使用 SQLite 和 Mock AI；完整基线为 `ruff check .` + `pytest`。
- 前端使用 Vitest 组件/Store/API 测试；覆盖长耗时请求超时、解析上传、AI 链路错误态等。
- 浏览器 E2E（Playwright）覆盖：
  - `core-flow.spec.ts`：注册、建会、资料上传、记录标记、知识库检索、记忆保存；
  - `ai-flow.spec.ts`：会前准备、会议问答、纪要生成、行动项确认转任务、问题提取（真实模型）；
  - `audio-flow.spec.ts`：音频上传与转写成功/未配置失败路径；
  - `local-workspace.spec.ts`：浏览器不支持目录访问时的降级提示。
- 真实模型 smoke 由 `backend/scripts/check_ai.py`、`check_rag.py` 单独执行，不等同于 Mock/API 测试。
- 本地目录授权与真实读写无法自动化，按 `docs/test-reports/local-workspace-manual-acceptance.md` 人工验收；不得把未执行项描述为已通过。
