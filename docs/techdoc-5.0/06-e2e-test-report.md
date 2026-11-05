# 06 E2E 测试报告（Playwright）

> 本轮仅修复测试代码与测试基础设施；**未修改 `backend/app/`、`frontend/src/` 及数据库/接口**。

## 一、测试代码基线

| 项 | 值 |
| --- | --- |
| 仓库 HEAD | `ff426413ef239e7f23133de206c402cab0b1d2a6`（`main`） |
| 业务代码 | 未改动（`git diff` 仅含 `frontend/e2e/`、`frontend/tests/router.spec.ts`） |
| 测试代码改动 | 已跟踪 7 个文件 +241 / −366（`support.ts` 与 5 个既有 spec + `router.spec.ts`）；新增未跟踪 `task-closure.spec.ts`（64 行） |
| 新增测试基础设施 | `tests/`（compose、mock-ai、scripts、README），未跟踪 |

## 二、测试环境

| 项 | 值 |
| --- | --- |
| 测试后端 | `openmind-test-backend-1`：8010，`ALLOW_GLOBAL_FALLBACK=true`，LLM/Embedding/ASR 均指向 Mock |
| 测试数据库 | **`openmind-db-test`**（PG16+pgvector，55432，独立卷），head `0022_audio_segments` |
| Mock AI/ASR | `openmind-test-mock-ai-1`：9000，FastAPI，OpenAI 兼容 |
| 测试前端 | `openmind-frontend-test`：5174，`VITE_API_BASE_URL=http://localhost:8010/api/v1` |
| Playwright | 1.64.1（宿主 `--no-save` 安装） |
| 浏览器 | Microsoft Edge **156.0.4314.58**（`E2E_CHANNEL=msedge`） |
| 开发环境 | 8001/5432/5173 未触碰；生产库未连接 |

## 三、执行命令与结果

```bash
cd frontend
E2E_BASE_URL=http://localhost:5174 \
E2E_API_BASE=http://localhost:8010/api/v1 \
E2E_CHANNEL=msedge E2E_EXPECT_ASR=1 \
npx playwright test --reporter=line
```

| 轮次 | spec | case | 通过 | 失败 | 跳过 | 耗时 | 退出码 | 日志 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 6 | 6 | 6 | 0 | 0 | 50.4 s | 0 | `test-logs/e2e-run-1.log` |
| 2 | 6 | 6 | 6 | 0 | 0 | 45.8 s | 0 | `test-logs/e2e-run-2.log` |
| 3 | 6 | 6 | 6 | 0 | 0 | 49.2 s | 0 | `test-logs/e2e-run-3.log` |

- 修复前失败的 `core-flow` 证据：`test-logs/e2e-core-flow.log`（`waiting for ...button{name:'保存'}` 超时）。
- 最终 3 轮无失败，无新增失败截图/trace；修复过程产生的截图与 trace 位于 `frontend/test-results/`（Playwright 默认产物，可 `npx playwright show-trace` 查看）。

## 四、用例清单（6 spec / 6 case）

| spec | 用例 | 覆盖 |
| --- | --- | --- |
| `core-flow.spec.ts` | 注册、建会、上传材料、会议详情与任务页 | 登录态、创建会议、材料解析、会议详情、任务入口 |
| `ai-flow.spec.ts` | 材料检索问答（带来源）与待办提取 | RAG 问答、来源、行动项候选（Mock 模型） |
| `audio-flow.spec.ts` | 上传音频→转写→编辑→确认生成会议记录 | 音频上传、转写状态、编辑文稿、确认入记录 |
| `model-settings.spec.ts` | 设置菜单保存自定义 LLM 配置并掩码回显 | 设置菜单、BYOK 保存、掩码、不回显明文 |
| `local-workspace.spec.ts` | 浏览器不支持目录访问时给出明确降级提示 | 本地工作区能力降级 |
| `task-closure.spec.ts` | 行动项确认→转任务→任务状态更新→刷新持久化 | 纪要提取/确认、转个人任务、任务列表、状态更新与持久化 |

## 五、第一步：真实界面核对（先查再改）

通过 Playwright 实际抓取 DOM（临时探针用例，已删除），确认：

1. 新建会议对话框：`role=dialog[aria-label=新建会议]`，输入 `#meeting-title`、`#meeting-topic`、`#meeting-time`，提交按钮文本 **“创建”**（编辑态才是“保存”）。
2. 创建成功后跳转 **`/new-meeting?meetingId=...`**，显示三段式工作区（资料预处理 / 实时录音转写 / 会后智能处理）。
3. 资料预处理：`input[type=file][accept*=txt]` 选文件后需点击 **“上传资料”**，状态徽标为 **“已解析”**。
4. 设置入口：左下角 `<summary aria-label="设置菜单">` 展开后为 `role=menuitem` 的“模型配置 / 记忆中心 / 知识库”。
5. 模型配置弹窗 `role=dialog[aria-label=模型配置]`：`#model-provider`（含“自定义（OpenAI 兼容）”，value=`custom`）、`#model-api-key`，自定义时 `#model-custom-base`、`#model-custom-model`，按钮“保存配置”。
6. **Embedding 无用户自备入口**：弹窗仅 LLM 三字段；Embedding 由服务端统一配置（`#embedding-*` 已不存在）。
7. 音频页：`input[type=file]` 上传后出现“已转写”“编辑文稿”（`#asr-transcript` + “保存修改”）、“确认并保存为记录”。
8. 会议问答：`#agent-chat-input` + “发送消息”，回复渲染在对话区。

## 六、发现的问题与修复

| # | 问题 | 处理 |
| --- | --- | --- |
| P1 | 用例仍在点“保存”，实际为“创建” | 改为 `getByRole('button',{name:'创建'})` |
| P2 | 建会后跳转 `/new-meeting`，用例仍期望停留列表 | `createMeeting` 返回 meetingId，并等待 `waitForURL` |
| P3 | 设置入口由链接改为“设置菜单” | 新增 `openModelConfig()`，用 `getByLabel('设置菜单')` + `menuitem` |
| P4 | `model-settings` 仍填 `#embedding-*`（5.0 已移除） | 重写为仅 LLM、自定义提供商；“Embedding 服务端统一”作为事实记录 |
| P5 | 材料上传只选文件未点“上传资料” | `uploadMaterial` 增加点击“上传资料” |
| P6 | 会议详情/本地工作区入口变化 | 详情走 `/meetings/:id`；降级用例改为在“材料”标签页断言 |
| P7 | 概览页标题由“会议工作台”改为“OpenMIND 智能会议助手” | `register()` 断言更新 |
| P8 | 预处理首屏加载慢（1.5s 抓取为空） | 非产品缺陷，改用 `getByRole('heading').waitFor` 条件等待，不用固定 sleep |

**未发现业务功能缺陷**；上述均为测试代码与 UI 不一致。

## 七、测试环境配置变更说明（基础设施）

- `tests/compose.test.yml`：数据库名由 `openmind` 统一为 **`openmind-db-test`**（`POSTGRES_DB` 与 `DATABASE_URL` 同步）；移除会被 `npm ci` 阻塞的 `frontend-test` 服务（改由 `docker run` 复用已安装卷）。
- 该文件曾因 PowerShell 编码回写导致 `ALLOW_GLOBAL_FALLBACK` 行被并入注释，已用 UTF-8 重写修复；修复后校验容器内 `ALLOW_GLOBAL_FALLBACK=true`、`llm_source=global`。
- 变更仅影响 `openmind-test` 项目；开发库（`openmind-db-1`，5432）与生产库未触碰。

## 八、数据库名称核对结果

| 项 | 结果 |
| --- | --- |
| 原配置数据库名 | `openmind`（服务名 `db-test`） |
| 现配置数据库名 | **`openmind-db-test`**（`POSTGRES_DB`、`DATABASE_URL`、healthcheck、README 一致） |
| 迁移 | 在新库执行 `alembic upgrade head` → `0022_audio_segments` |
| PG 集成复跑（新库） | **13/13 passed**（`test-logs/pg-integration-openmind-db-test.log`） |
| 重启持久性 | `persist-check rows = 1` |
| 旧库 | 保留未删（历史测试数据），不影响新库 |

## 九、FunASR 检查（未启动，单独记录）

| 项 | 结果 |
| --- | --- |
| 资源 | 24 逻辑核、31.7 GB 内存、D 盘剩余 113.9 GB |
| 镜像/容器 | 无 `asr`/`funasr` 镜像与容器 |
| 结论 | **未启动**：需构建 `docker/asr`（torch+funasr，模型约 1.5 GB，CPU 首次预热约 15 分钟）。本轮不阻塞 E2E；真实 FunASR 转写仍未验证，Mock ASR 结果不替代真实转写 |

## 十、尚未解决

1. A 组未执行真实 LLM/Embedding 供应商、真实外部 ASR、真实本地 FunASR（无凭据/未构建）；队友 B 组记录见 `04-test-evidence.md` 第九节。
2. 浏览器实时录音（MediaRecorder）与本地目录真实写入需人工授权，未纳入自动 E2E，列为人工验收项。
3. ~~行动项“确认→转任务→任务状态更新”的 UI 路径未覆盖~~ —— 已由新增 `task-closure.spec.ts` 覆盖并通过（6/6）。
4. `npm ci` 在本机仍报 npm 内部错误（环境问题），测试前端依赖卷副本。

## 十一、Git diff 与基线

```
HEAD: ff426413ef239e7f23133de206c402cab0b1d2a6 (main)
frontend/e2e/ai-flow.spec.ts          |  83 +++---------
frontend/e2e/audio-flow.spec.ts       |  52 ++++----
frontend/e2e/core-flow.spec.ts        |  77 ++++-------
frontend/e2e/local-workspace.spec.ts  |  17 ++-
frontend/e2e/model-settings.spec.ts   |  88 +++++-------
frontend/e2e/support.ts               | 250 +++++++++++++----------------------
frontend/tests/router.spec.ts         |  15 +++
7 files changed, 241 insertions(+), 366 deletions(-)
+ 未跟踪新增：frontend/e2e/task-closure.spec.ts（64 行）
+ 未跟踪新增：tests/（compose.test.yml、mock-ai/app.py、scripts/*.py、README.md、storage-test/）
```

**未提交（未执行 git commit）**；本轮仅修复测试代码与基础设施，等待独立复核后再决定提交。

## 十二、队友补充 E2E（不同轮次，不合并）

- 队友在清理提交 `e38fe2a`（不在本仓库历史中）另跑 E2E：**2 passed / 3 skipped / 0 failed**；3 skipped 为模型凭据受限（BLOCKED），属设计内降级。
- 该轮为 5 case 套件、队友环境，与本报告 A 组（`ff42641`，6 case，6/6×3）不是同一轮次，二者不合并、不互相替代。
- skipped 不得计为 passed；本报告 A 组结果仍为 6/6×3（Mock 环境）。
