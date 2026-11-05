# 04 测试执行记录与证据（test-evidence）

> 基线：`main` @ `ff42641`（`ff426413ef239e7f23133de206c402cab0b1d2a6`）；执行日期：2026-11-02 至 2026-11-03；执行环境：Docker 容器单元测试 + 独立测试栈（Mock HTTP + 真实 PostgreSQL）+ 宿主 Playwright。

## 一、环境

| 项 | 值 |
| --- | --- |
| 开发环境（未动） | backend 8001、db 5432、frontend 5173 |
| 测试编排 | `tests/compose.test.yml`（项目 `openmind-test`） |
| 测试数据库 | **`openmind-db-test`**（PG16 + pgvector，55432，独立卷），head `0022_audio_segments` |
| 测试后端 | `openmind-test-backend-test-1`：8010，`ALLOW_GLOBAL_FALLBACK=true`，LLM/Embedding/ASR 均指向 Mock |
| Mock AI/ASR | `openmind-test-mock-ai-1`：9000，FastAPI，OpenAI 兼容（模式 `normal/429/500/401/402/invalid_json/dim_mismatch`） |
| 测试前端 | `openmind-frontend-test`：5174，`VITE_API_BASE_URL=http://localhost:8010/api/v1` |
| E2E | 宿主 `@playwright/test@1.64.1`（`--no-save`），Microsoft Edge **156.0.4314.58** |
| 单元测试库 | 后端 pytest 使用 SQLite 内存库，`indexing_service.embed_texts` monkeypatch 为 1024 维零向量 |

## 二、后端

| 命令 | 退出码 | 通过 | 失败 | 跳过 | 耗时 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| `docker exec openmind-backend-1 python -m pytest` | 0 | **350** | 0 | 0 | 115.49 s | `350 passed, 1 warning` |
| `docker exec openmind-backend-1 ruff check .` | 0 | — | — | — | — | `All checks passed!` |

- 测试文件 36 个（`backend/tests/{unit,api}`）。
- 性质：Mock/内存库单元与接口测试（非真实模型、非真实 PostgreSQL）；真实 LLM/Embedding/RAG 质量未执行。

## 三、前端

### 3.1 完整执行（连续 5 次）

| 命令 | 退出码 | 测试文件 | 通过 | 失败 | 总用例 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| `docker exec openmind-frontend-1 npm run test`（×5） | 0×5 | 87 | **449** | **0** | 449 | 每次 `449 passed` |

日志：`vitest-run-1.log` … `vitest-run-5.log`。

### 3.2 历史失败与修复（如实保留）

- **修复前**：`447 passed + 2 failed`，均为 `tests/router.spec.ts > router guard` 的 `protects the tasks route`、`protects the new meeting stages`，`Test timed out in 5000ms`。
- **根因**：`src/router/index.ts` 路由懒加载；`router.push()` 在 87 文件并行时编译目标 SFC 及其依赖超过默认 5 s。非守卫/Pinia 逻辑缺陷。
- **修复（仅测试代码）**：`router.spec.ts` 将懒加载组件 `vi.mock` 为 `render: () => null` 的轻量 stub；未调大 timeout。
- **修复后**：单用例 18 ms、整文件 12/12、连续 5 次全量 449/449。
- 修复前日志：`vitest-2026-11-02.log`、`vitest-before-fix-tasks.log`。

### 3.3 其他前端检查

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm run typecheck` | 0 | 通过 |
| `npm run lint` | 0 | 通过 |
| `npm run build` | 0 | 通过 |

## 四、独立测试栈（Mock HTTP + 真实 PostgreSQL）

| 套件 | 命令（容器内） | 结果 | 日志 |
| --- | --- | --- | --- |
| PostgreSQL 集成 | `pg_integration.py` | **13/13 passed** | `pg-integration.log` |
| PG 重启持久性 | 重启 db-test 后 `check_persist.py` | `rows = 1` | `pg-persistence-after-restart.log` |
| AI Mock 全链路 | `ai_mock_checks.py` | **22/22** | `ai-mock-checks.log` |
| 音频 Mock | `audio_mock_checks.py` | **17/17** | `audio-mock-checks.log` |
| 安全 | `security_checks.py` | **14/14** | `security-checks.log` |
| SSRF | `ssrf_checks.py`（`ALLOW_PRIVATE_MODEL_ENDPOINTS=false`） | **6/6** | `ssrf-checks.log` |
| Fallback 默认关闭 | `fallback_default_off.py`（`ALLOW_GLOBAL_FALLBACK=false`） | **4/4** | `fallback-default-off.log` |

## 五、浏览器 E2E（Mock 环境）

| 轮次 | spec | case | 通过 | 失败 | 耗时 | 退出码 | 日志 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 6 | 6 | **6** | 0 | 50.4 s | 0 | `e2e-run-1.log` |
| 2 | 6 | 6 | **6** | 0 | 45.8 s | 0 | `e2e-run-2.log` |
| 3 | 6 | 6 | **6** | 0 | 49.2 s | 0 | `e2e-run-3.log` |

- 覆盖：核心闭环、AI 问答/待办提取、音频上传→转写→确认、BYOK 保存/掩码、本地工作区降级、任务闭环（行动项确认→转任务→状态更新→刷新持久化）。
- 脚本：`frontend/e2e/{core-flow,ai-flow,audio-flow,model-settings,local-workspace,task-closure}.spec.ts` + `support.ts`。
- 环境：Mock 模型 + 真实后端 + 真实 PostgreSQL；浏览器 Edge。

## 六、验证边界（如实标注）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| E2E（Mock 环境） | 已执行 | 6/6，连续 3 轮 |
| 真实供应商 LLM/Embedding | 未执行 | 无可用且已充值密钥 |
| 真实外部 ASR / 本地 FunASR | 未执行 | 无外部凭据；asr 镜像与模型未构建/下载 |
| 浏览器实时录音（MediaRecorder） | 未执行 | 需人工授权麦克风 |
| 本地工作区真实写入 | 未执行 | 需人工选择目录 |
| RAG 准确率/召回率、并发/QPS | 未验证 | 无标注评测集、未压测 |

## 七、历史与口径说明

- 4.1 基线（`7454a20`）历史记录：后端 304、前端 403（401+2），非 5.0 结果，不作当前依据。
- 本文件所有 5.0 数字均来自 `ff42641` 上的实际执行。
- Mock 测试不等于真实模型测试；逐例/整文件复跑通过不等于全量通过；E2E 文件存在不等于已执行（本轮已实际执行）。
- 开发环境 8001/5432/5173 未被测试触碰。

## 八、复现命令汇总

```bash
# 单元/接口
docker exec openmind-backend-1 ruff check .
docker exec openmind-backend-1 python -m pytest
docker exec openmind-frontend-1 npm run typecheck
docker exec openmind-frontend-1 npm run lint
docker exec openmind-frontend-1 npm run test
docker exec openmind-frontend-1 npm run build

# 独立测试栈
docker compose -f tests/compose.test.yml up -d db-test mock-ai backend-test
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/pg_integration.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/ai_mock_checks.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/audio_mock_checks.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/security_checks.py

# 浏览器 E2E（宿主）
cd frontend
E2E_BASE_URL=http://localhost:5174 E2E_API_BASE=http://localhost:8010/api/v1 \
E2E_CHANNEL=msedge E2E_EXPECT_ASR=1 npx playwright test --reporter=line
```

## 九、队友补充测试（B 组，独立记录）

- **来源**：`tests/队友测试补充报告.doc`（原件保留未改）；对应队友清理提交 `e38fe2a`（不在本仓库历史中）。
- **性质**：补充证据，不与本文件 A 组（`ff42641`）数据合并；下列数字**仅依据队友报告记录，未在本仓库独立复测**。
- **环境**：队友环境（含真实 GLM-4-Flash 与本地 FunASR）。

| 类别 | 检查 | 结果 | 说明 |
| --- | --- | --- | --- |
| 自动化单元/组件 | 后端 pytest | 349 passed（120.8 s），exit 0 | 清理提交删除 1 例 |
| 质量门禁 | 后端 ruff | 通过 | — |
| 自动化单元/组件 | 前端 Vitest | 438 passed / 85 文件，连续 3 轮，exit 0 | 清理提交删除 11 例 |
| 质量门禁 | typecheck / lint / build | 全部通过 | — |
| E2E | Playwright | 2 passed / 3 skipped / 0 failed | 3 skipped 为模型凭据受限（BLOCKED），不计为通过 |
| 真实 LLM | GLM-4-Flash | 2 次调用成功 | 真实供应商 |
| 真实 Embedding | 出网调用 | RATE_LIMITED ×2 | 未成功 |
| 真实 ASR | FunASR | 转写→确认→生成记录成功 | 真实本地服务 |

**未验收/受限（B 组同样未覆盖）**：实时录音人工验收、本地工作区真实目录读写、RAG 检索质量评测、真实 Embedding 成功调用；E2E 3 项为 skipped。

B 组与本仓库 A 组的 pytest（349 vs 350）、Vitest（438/85 vs 449/87）与 E2E（2+3 skipped vs 6/6）分属不同提交与环境，**不得拼接为一组成绩**。
