# 05 系统测试报告（system-test-report）

> 代码基线：`main` @ `ff426413ef239e7f23133de206c402cab0b1d2a6`；测试日期：2026-11-02。
> 说明：本轮为测试任务，**未修改 `backend/app/` 与 `frontend/src/` 业务代码**；仅修改测试文件 `frontend/tests/router.spec.ts`，并新增测试基础设施 `tests/`。

## 一、环境

| 项 | 值 |
| --- | --- |
| 开发环境（未动） | backend 8001、db 5432、frontend 5173 |
| 测试编排 | `tests/compose.test.yml`（项目 `openmind-test`） |
| 测试数据库 | `openmind-test-db-test-1`，PostgreSQL16 + pgvector，宿主机 55432，独立卷 |
| 测试后端 | `openmind-test-backend-test-1`，宿主机 8010，`ALLOW_GLOBAL_FALLBACK=true`，AI 全部指向 Mock |
| Mock AI/ASR | `openmind-test-mock-ai-1`，FastAPI，宿主机 9000（`/v1/chat/completions`、`/v1/embeddings`、`/v1/models`、`/v1/audio/transcriptions`） |
| 测试前端 | `openmind-frontend-test`，宿主机 5174，`VITE_API_BASE_URL=http://localhost:8010/api/v1` |
| E2E 运行器 | 宿主 `@playwright/test@1.64.1`（`--no-save` 装入 `frontend/node_modules`），浏览器 Microsoft Edge |
| 迁移 | 空库执行 `alembic upgrade head`：`0001 → 0022_audio_segments` |

## 二、结果总表（按证据类型区分）

| 套件 | 类型 | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- | --- |
| 后端 pytest | Mock/内存库 | `python -m pytest` | 0 | 350 passed, 1 warning（115.49s） |
| 后端 ruff | 静态检查 | `ruff check .` | 0 | All checks passed |
| 前端 Vitest ×5 | Mock/单元 | `npm run test`（连续 5 次） | 0×5 | 每次 449 passed / 87 files |
| PostgreSQL 集成 | **真实 PG** | `python /tests/scripts/pg_integration.py` | 0 | 13/13 passed |
| PG 重启持久性 | **真实 PG** | 重启 db-test 后 `check_persist.py` | 0 | persist-check rows = 1 |
| AI Mock 全链路 | **Mock HTTP** | `python /tests/scripts/ai_mock_checks.py` | 0 | 22/22 passed |
| 音频 Mock | **Mock HTTP** | `python /tests/scripts/audio_mock_checks.py` | 0 | 17/17 passed |
| 安全测试 | HTTP + 单元 | `python /tests/scripts/security_checks.py` | 0 | 14/14 passed |
| SSRF 校验 | 配置级 | `ssrf_checks.py`（`ALLOW_PRIVATE_MODEL_ENDPOINTS=false`） | 0 | 6/6 passed |
| Fallback 默认关闭 | 配置级 | `fallback_default_off.py`（`ALLOW_GLOBAL_FALLBACK=false`） | 0 | 4/4 passed |
| Playwright E2E | 真实浏览器 + Mock | `npx playwright test` | 1 | **失败：用例与 5.0 UI 不一致**（见缺陷 D1） |
| 真实供应商 LLM/Embedding | 真实外部 | — | — | **未执行**（无已充值密钥） |
| 真实 ASR / FunASR | 真实外部/本地 | — | — | **未执行**（asr 镜像与模型未构建/下载） |
| 浏览器人工验收（实时录音） | 人工 | — | — | **未执行** |

## 三、关键套件详情

### 3.1 前端 Vitest 超时根因与修复

- **修复前**：全量 447 passed + 2 failed（`protects the tasks route`、`protects the new meeting stages`，`Test timed out in 5000ms`）；单用例 `-t` 复跑时好时坏（2602ms 通过 / 5000ms 超时）。
- **根因**：`vite.config.ts` 未设 `testTimeout`（默认 5000ms）；`src/router/index.ts` 所有路由为 `() => import('@/views/...')` 懒加载；`router.spec.ts` 的 `router.push()` 会真正编译 `WorkspaceLayout` 与目标视图 SFC 及其传递依赖。全量 87 个测试文件并行时 CPU 竞争使编译超过 5s。**不是守卫或 Pinia 逻辑缺陷**。
- **修复（仅测试代码）**：在 `frontend/tests/router.spec.ts` 中把懒加载组件 `vi.mock` 为轻量 stub（`render: () => null`），保留真实 router/守卫/Pinia/mock；未调大 timeout。
- **修复后**：单用例 18ms；整文件 12/12；**连续 5 次全量均 449 passed / 87 files**。
- 日志：`vitest-2026-11-02.log`（修复前）、`vitest-before-fix-tasks.log`、`vitest-run-1..5.log`。

### 3.2 PostgreSQL 集成（真实）

覆盖：迁移 head 0022、ORM 表/列与迁移一致（16/16）、用户隔离、会议/材料/行动项/任务 CRUD、JSONB 分段读写与 `segments->1->>'text'` 路径查询、外键约束、`action_id` 唯一约束、事务回滚、重启持久性。13/13 + 重启 1 行。
日志：`pg-integration.log`、`pg-persistence-after-restart.log`。

### 3.3 AI Mock 全链路

覆盖：默认来源 global、BYOK 保存/掩码/明文不泄漏、LLM 正常与 429/500/401/402/非法 JSON 映射、Embedding 正常与维度错误、RAG 返回来源与 Top-K≤5、knowledge_base 无证据拒答、整理链 summary/brief/polish/organize、删除 BYOK 回退。
日志：`ai-mock-checks.log`（22/22）。

### 3.4 音频 Mock

覆盖：上传转写、类型 415、大小 413、实时会话、分片逐片转写、序号不连续 422、单片失败不中断 + 重试、分段标记、结束合并与临时分片清理、转写编辑重拆段、确认生成记录、重复确认幂等、已确认不可删除 409、跨用户 404、未确认可删除。
日志：`audio-mock-checks.log`（17/17）。

### 3.5 安全

未登录 401、跨用户 404、材料类型 415、大小 413、路径穿越中和、BYOK 明文不泄漏、JWT 过期 401、归档后写 409、非法任务流转 409、合法流转、重复转任务幂等。14/14。
SSRF：拦截回环/私网/元数据地址/ftp，放行公网 HTTPS。6/6。
日志：`security-checks.log`、`ssrf-checks.log`。

### 3.6 Fallback 默认关闭（独立容器）

`ALLOW_GLOBAL_FALLBACK=false` 且无 BYOK：`resolve_model_config` 的 LLM 为空，调用抛 `MODEL_CONFIG_REQUIRED/400`；Embedding 仍取服务端配置。4/4。
日志：`fallback-default-off.log`。

## 四、缺陷清单

### D1（测试代码缺陷，已修复）：E2E 用例未随 5.0 UI 改版更新

- **现象**：`core-flow` 失败：`waiting for getByRole('dialog',{name:'新建会议'}).getByRole('button',{name:'保存'})` 超时。
- **原因（代码证据）**：
  1. `MeetingFormDialog.vue` 新建时提交按钮文案为 **“创建”**（`submitLabel = isEditing ? '保存' : '创建'`），用例仍点“保存”。
  2. `DashboardView.createMeeting` 创建成功后 `router.push({name: newMeeting, query:{meetingId}})`，用例仍期望停留在列表页并看到标题按钮。
  3. 设置入口由旧的“系统设置/模型配置”链接改为左下角 `设置菜单`（`<details>` + `<button role=menuitem>`）；且 `ModelConfigDialog` 只有 LLM 字段，`model-settings.spec.ts` 仍填写已删除的 `#embedding-*`。
  4. 概览页标题由“会议工作台”改为 `OpenMIND 智能会议助手`（已在 `support.ts` 修正）。
- **影响**：E2E 全部用例在 `createMeeting` 处失败，无法覆盖登录/建会/材料/纪要/转任务/音频。
- **处理建议**：按 5.0 三段式工作区与设置菜单重写 E2E 选择器（属测试代码，需单独排期）。**本轮不修改业务代码，也不伪造通过。**
- **处理结果（2026-11-03）**：已按 5.0 UI 重写 `support.ts` 与 6 个 spec，并新增任务闭环用例；连续 3 轮 6/6 通过（详见 `06-e2e-test-report.md`）。未修改业务代码。
- 日志：`e2e-core-flow.log`。

### D2（测试代码缺陷，已修复）：Vitest 路由单测超时

见 3.1，已通过 stub 懒加载组件修复，5 次全量 449 全绿。

### D3（环境问题，已绕过）：`npm ci` 构建测试前端失败

- **现象**：`docker compose build frontend-test` 时 `npm ci` 报 `Exit handler never called!`（npm 内部错误）。
- **绕过**：复制已有 `openmind_frontend_node_modules` 卷为新卷，用 `openmind-frontend:latest` + 挂载方式启动 5174，未改 Dockerfile/业务代码。

### 业务缺陷

- **本轮已执行套件（后端 350、PG 13、AI 22、音频 17、安全 14、SSRF 6、Fallback 4）未发现业务功能缺陷。**

## 五、未执行 / 受阻项（如实标注）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| 真实供应商 LLM/Embedding | 未执行 | 无可用且已充值密钥；本轮用本地 Mock |
| 真实外部 ASR | 未执行 | 无外部 ASR 凭据 |
| 本地 FunASR 真实转写 | 未执行 | 未构建 asr 镜像、未下载模型（镜像/模型约 1.5GB+，CPU 预热约 15 分钟） |
| 浏览器实时录音（MediaRecorder + 分片） | 未执行 | 需人工授权麦克风；E2E 的音频用例是文件上传，非实时录音 |
| 人工浏览器验收（本地工作区写入） | 未执行 | 需 Chromium 人工选目录 |
| Playwright E2E 全链路 | 已执行 | 6/6，连续 3 轮（Mock 环境，Edge） |

## 六、原始日志清单（`docs/techdoc-5.0/test-logs/`）

`pytest-2026-11-02.log`、`ruff-2026-11-02.log`、`vitest-2026-11-02.log`（修复前 447+2）、`vitest-before-fix-tasks.log`、`vitest-run-1.log`…`vitest-run-5.log`、`pg-integration.log`、`pg-persistence-after-restart.log`、`ai-mock-checks.log`、`audio-mock-checks.log`、`security-checks.log`、`ssrf-checks.log`、`fallback-default-off.log`、`e2e-core-flow.log`。

## 七、复现说明

见 `tests/README.md`。要点：

```bash
docker compose -f tests/compose.test.yml up -d db-test mock-ai backend-test
# 测试前端（因 npm ci 环境问题，使用已安装卷副本）
docker run -d --name openmind-frontend-test \
  -v "<repo>/frontend:/app" -v frontend_node_modules_test:/app/node_modules \
  -p 127.0.0.1:5174:5173 \
  -e VITE_API_BASE_URL=http://localhost:8010/api/v1 \
  -e VITE_DEV_PROXY_TARGET=http://host.docker.internal:8010 \
  openmind-frontend:latest
# 各套件
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/pg_integration.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/ai_mock_checks.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/audio_mock_checks.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/security_checks.py
docker compose -f tests/compose.test.yml run --rm -e ALLOW_PRIVATE_MODEL_ENDPOINTS=false -e PYTHONPATH=/app backend-test python /tests/scripts/ssrf_checks.py
docker compose -f tests/compose.test.yml run --rm -e ALLOW_GLOBAL_FALLBACK=false -e PYTHONPATH=/app backend-test python /tests/scripts/fallback_default_off.py
```

## 八、结论

- 已完成并能稳定复现的：后端 350、Vitest 449×5、PG 真实集成 13、AI Mock 22、音频 17、安全 14、SSRF 6、Fallback 4。
- E2E 用例已按 5.0 UI 重写并实际执行：6/6，连续 3 轮通过（Mock 环境，Edge）。
- 真实供应商、真实 ASR、实时录音、人工工作区验收仍未执行，文档继续如实标注；最终 PDF 已同步（22 页）。

## 九、补充（2026-11-03）：E2E 重写与任务闭环

- 测试代码：重写 `frontend/e2e/support.ts` 与 6 个 spec；新增 `task-closure.spec.ts`，覆盖“会议记录 → 纪要提取行动项 → 确认 → 转为我的个人任务 → 任务页状态更新 → 刷新持久化 → 回会议详情确认已转任务”。
- 结果：**6 spec / 6 case，连续 3 轮 6/6**（50.4 s / 45.8 s / 49.2 s，exit 0）；日志 `test-logs/e2e-run-1.log`…`e2e-run-3.log`。
- 环境：Mock 模型 + 真实后端 + 真实 PostgreSQL `openmind-db-test`；浏览器 Edge 156.0.4314.58。
- 未改动 `backend/app/`、`frontend/src/`；开发环境 8001/5432/5173 未触碰。

## 十、队友补充测试记录（B 组，不与本轮 A 组合并）

- 来源：`tests/队友测试补充报告.doc`，对应清理提交 `e38fe2a`（不在本仓库历史中）；仅依据报告记录，未独立复测。
- 结果：pytest 349 passed（120.8 s）、Vitest 438 passed/85 文件×3、E2E 2 passed/3 skipped/0 failed、真实 GLM-4-Flash 2 次成功、Embedding RATE_LIMITED×2、FunASR 全流程成功。
- 与本轮 A 组（pytest 350、Vitest 449×5、E2E 6/6×3）分属不同版本与环境，文档中分组列示、不合并。
- 未验收项不变：实时录音、本地工作区真实读写、RAG 质量评测、真实 Embedding 成功调用。
