# OpenMIND 5.0 测试复执行报告

> 性质：审查期间的独立复核，不构成第四阶段完成或最终验收。
> 基线：`ff426413ef239e7f23133de206c402cab0b1d2a6`（`main`，与 `origin/main` 相同）。

## 一、工作区与分支

| 项 | 状态 |
| --- | --- |
| 分支 | `main`（未切换、未 reset/rebase/merge） |
| HEAD | `ff426413ef239e7f23133de206c402cab0b1d2a6` |
| `origin/main` | `ff426413ef239e7f23133de206c402cab0b1d2a6` |
| `origin/develop` | `7454a2025429656211b756f761a6eb4d6848f88d` |
| 业务代码改动 | 无（`backend/app`、`frontend/src` 工作区干净） |
| 未提交改动 | 既有 E2E/support/router.spec 修改；本次新增 2 个 spec、修改 1 个 spec；文档与测试基础设施未跟踪，均保留 |

## 二、环境

| 项 | 值 |
| --- | --- |
| 宿主 | Windows / PowerShell 5.1；Docker Desktop（本次启动） |
| 后端（单测） | `openmind-backend-1`，Python 3.13.16，FastAPI 0.150.0 |
| 前端（单测） | `openmind-frontend-1`，Node v22.23.2，Vitest 2.1.9 |
| 测试后端 | `openmind-test-backend-test-1`：8010，LLM/Embedding/ASR 全部指向 `mock-ai:9000` |
| 测试数据库 | `openmind-db-test`，PostgreSQL 16.15 + pgvector 0.8.7，head `0022_audio_segments` |
| Mock AI/ASR | `openmind-test-mock-ai-1`：9000（OpenAI 兼容） |
| 测试前端 | `openmind-frontend-test`：5174 |
| E2E | 宿主 Playwright 1.64.1，Microsoft Edge |

## 三、执行结果

| 套件 | 命令 | 结果 | 退出码 | 日志 |
| --- | --- | --- | --- | --- |
| 后端 ruff | `docker exec openmind-backend-1 ruff check .` | All checks passed | 0 | `logs/backend-ruff.log` |
| 后端 pytest | `docker exec openmind-backend-1 python -m pytest` | collected **350**；**350 passed**、0 failed、0 skipped、0 errors；1 warning；98.94s | 0 | `logs/backend-pytest.log` |
| 前端 typecheck | `npm run typecheck` | 通过 | 0 | `logs/frontend-typecheck.log` |
| 前端 lint | `npm run lint` | 通过 | 0 | `logs/frontend-lint.log` |
| 前端 Vitest ×5 | `npm run test`（连续 5 次） | 每次 **87 files / 449 passed**，0 failed/skipped | 0×5 | `logs/frontend-vitest*.log` |
| 前端 build | `npm run build` | 通过（8.13s） | 0 | `logs/frontend-build.log` |
| PostgreSQL 集成 | `pg_integration.py` | **13/13** | 0 | `logs/pg-integration.log` |
| PG 重启持久性 | 重启 `db-test` 后 `check_persist.py` | `rows = 1` | 0 | `logs/pg-persistence.log` |
| AI Mock | `ai_mock_checks.py` | **22/22** | 0 | `logs/ai_mock_checks.log` |
| 音频 Mock | `audio_mock_checks.py` | **17/17** | 0 | `logs/audio_mock_checks.log` |
| 安全 | `security_checks.py` | **14/14** | 0 | `logs/security_checks.log` |
| SSRF | `ssrf_checks.py`（allow_private=false） | **6/6** | 0 | `logs/ssrf_checks.log` |
| Fallback | `fallback_default_off.py`（ALLOW_GLOBAL_FALLBACK=false） | **4/4** | 0 | `logs/fallback_default_off.log` |
| E2E | `npx playwright test`（3 轮） | **8 passed / 0 failed / 0 skipped**，每轮 | 0×3 | `logs/e2e-round-1..3.log` |

Vitest 5 次耗时：22.65 / 30.78 / 29.22 / 28.26 / 27.45s。
E2E 3 轮耗时：约 1.3m / 53.6s / 48.8s。
新增 2 条 E2E 后已重跑 `typecheck` 与 `lint`，仍为 exit 0（`tsconfig.json` 的 `include` 含 `e2e/**/*.ts`）。

**路由单测专项**：`tests/router.spec.ts` 仅将懒加载视图 stub 为 `render: () => null`，真实 router/守卫/Pinia 保留，断言仍检查重定向与放行；视图渲染由 E2E 覆盖。未发现空断言或断言失效。连续 5 次全量均 87/87 文件、449/449 用例通过，未复现此前的 5000ms 超时。
### PostgreSQL / 迁移核验

- `PostgreSQL 16.15`；`vector 0.8.7`；`alembic_version = 0022_audio_segments`。
- 覆盖：ORM/迁移表列一致（16/16）、用户隔离、跨用户空结果、会议/材料/行动项/任务 CRUD、JSONB 分段与路径查询、外键、`action_id` 唯一、事务回滚、重启持久性。

### 真实与 Mock 边界

| 项 | 本轮状态 |
| --- | --- |
| LLM | **Mock**（`LLM_API_BASE=http://mock-ai:9000/v1`）；真实调用 BLOCKED（无凭据） |
| Embedding | **Mock**；真实调用 BLOCKED |
| ASR | **Mock**（`ASR_API_BASE=http://mock-ai:9000/v1`）；真实外部 ASR BLOCKED；本地 FunASR NOT RUN（无镜像/容器/模型） |
| 浏览器录音 | NOT RUN（需人工授权麦克风） |
| 本地工作区真实读写 | NOT RUN（需人工选择目录） |
| RAG 质量 | NOT EVALUATED（无标注评测集） |

## 四、E2E 明细

审查前仓库为 6 spec / 6 case（旧材料 5/5 为加入 `task-closure` 之前的状态）；本次补充 2 条缺口用例后为 **8 spec / 8 case**。

| # | spec | case | 断言要点 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | `ai-flow.spec.ts` | 材料检索问答与待办提取 | 回复含“根据会议记录与材料”、行动项内容 | 通过（原条件 skip 已改为断言） |
| 2 | `audio-flow.spec.ts` | 上传→转写→编辑→确认生成记录 | 状态/文稿/确认入记录 | 通过 |
| 3 | `auth-flow.spec.ts`（新增） | 注册后清除令牌并重新登录 | 登录页标题、URL `/dashboard` | 通过 |
| 4 | `core-flow.spec.ts` | 注册、建会、上传材料、详情、任务页 | 材料“已解析”、详情四个区块 | 通过 |
| 5 | `local-workspace.spec.ts` | 目录 API 不支持时降级提示 | 明确提示文案 | 通过 |
| 6 | `minutes-flow.spec.ts`（新增） | 生成纪要草稿并确认、刷新持久化 | 草稿→已确认；刷新后仍“已确认” | 通过 |
| 7 | `model-settings.spec.ts` | BYOK 保存与掩码 | 保存成功、不回显明文 | 通过 |
| 8 | `task-closure.spec.ts` | 行动项确认→转任务→状态更新→刷新持久化 | 任务出现、状态 `in_progress`、刷新后保持 | 通过 |

- 行动项确认→转任务→任务状态更新→刷新持久化：**真实通过**（连续 3 轮均通过）。
- 每轮原始日志已保留于 `logs/e2e-round-1..3.log`；Playwright HTML 报告默认覆盖，仅保留最后一轮。
- 未使用 `test.skip` / `test.fixme` / `waitForTimeout` / 空断言；异步均使用条件等待。
- 审前 `ai-flow` 的条件 `test.skip` 属于“环境不就绪即静默跳过”的设计隐患，已改为失败断言。

## 五、失败与处理

| 分类 | 数量 | 说明 |
| --- | --- | --- |
| A 业务代码缺陷 | 0 | 本轮未发现 |
| B 测试代码缺陷 | 1 | `ai-flow` 条件 skip；已改为断言 |
| C 环境/依赖 | 0 | Docker 启动后正常；`npm ci` 未使用 |
| D 外部凭据/额度 | 3 类 | 真实 LLM/Embedding/ASR 均 BLOCKED |
| E 测试设计不足 | 2 | 缺登录、缺纪要生成；已补 2 条 E2E |
| F 文档与实现不一致 | 见审查报告 | 主要是 README 基线与 B 组可复核性 |

本轮无测试失败；上述 B/E 为审查中发现并已处理的问题。未删除测试、未降低断言、未新增 skip。

## 六、原始日志

全部位于 `docs/test-review/logs/`：

`backend-ruff.log`、`backend-pytest.log`、`frontend-typecheck.log`、`frontend-lint.log`、`frontend-vitest.log`、`frontend-vitest-2..5.log`、`frontend-build.log`、`pg-integration.log`、`pg-persistence.log`、`ai_mock_checks.log`、`audio_mock_checks.log`、`security_checks.log`、`ssrf_checks.log`、`fallback_default_off.log`、`e2e-round-1..3.log`。

## 七、持久化断言强化与追加复核

- `task-closure.spec.ts`：刷新后从 `select#task-status-<id>` 提取 task_id，调用 `GET /api/v1/tasks/{task_id}`，断言 `task_id`、`title`、`status=in_progress` 均来自后端，不仅检查下拉框显示。
- `minutes-flow.spec.ts`：刷新并点击列表项后，调用 `GET /api/v1/meetings/{meeting_id}/minutes`，断言存在 `status=confirmed` 且 `content` 含“灰度发布”。
- `auth-flow.spec.ts`：登录后执行 `page.reload()`，仍停留 `/dashboard`，验证令牌持久化。
- 其余用例：core 断言材料“已解析”、详情区块；audio 断言转写/确认入记录；model-settings 断言保存成功与掩码回显；local-workspace 为降级提示（设计上无持久化数据）。
- 追加 3 轮：8/8（47.8s / 51.4s / 53.4s），日志 `logs/e2e-verify-1..3.log`；原 `e2e-round-1..3.log` 保留，未覆盖。
- 新增断言后重跑 `typecheck`/`lint`，均 exit 0。

## 八、E2E 覆盖恢复后的最终复核

- 恢复 core-flow 的记录标记、知识库上传/检索、记忆保存；恢复 ai-flow 的会前准备、纪要生成、问题提取；audio-flow 增加后端记录校验；model-settings 增加后端来源/掩码校验并移除不存在的 Embedding BYOK 断言。
- 最终 8 spec / 8 case，连续 3 轮 8/8（55.7 / 52.3 / 59.9 s），0 failed / 0 skipped。
- 日志：`logs/e2e-restored-final-1.log`…`e2e-restored-final-3.log`；调试与失败日志保留（`e2e-restore-debug.log`、`e2e-restored-1.log`、`e2e-core-debug.log`）。
- 覆盖差异详见 `e2e-coverage-diff.md`。
