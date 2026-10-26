# OpenMIND 集成测试与业务闭环验收报告

> 生成时间：2026-10-26
> 验收基线：`develop` @ `833e50f`（PR #52 合并后）
> 执行范围：最新代码 + 真实 PostgreSQL/pgvector + 真实 LLM/Embedding + 真实 HTTP 闭环。
> 结论口径：仅在实际执行并取得证据时标记 PASS；外部能力缺失标记 BLOCKED；未执行标记 SKIPPED。

## 一、环境信息

| 项目 | 值 |
| --- | --- |
| 宿主 | Windows + Docker Desktop |
| 数据库 | PostgreSQL 16 + pgvector 0.8.7，容器 `openmind-db-1` |
| 验证数据库 | 临时库 `openmind_acceptance`，验收后已删除 |
| 后端 | 最新代码，独立 uvicorn 进程 `127.0.0.1:8010` |
| 前端自动化 | Vitest + Vue Test Utils |
| 迁移 | 从空库升级到 `0018_meeting_audio (head)` |
| LLM / Embedding | 真实全局配置（仅验收进程临时开启 `ALLOW_GLOBAL_FALLBACK=true`） |
| ASR | 未配置 `ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL` |

## 二、自动化测试

| 检查 | 结果 |
| --- | --- |
| 后端 `ruff check .` | PASS |
| 后端 `pytest` | PASS，287 passed |
| 前端 `npm run typecheck` | PASS |
| 前端 `npm run lint` | PASS |
| 前端 `npm run test -- --run` | PASS，72 files / 361 tests |
| 前端 `npm run build` | PASS |

## 三、数据库迁移

- 在全新临时库执行 `alembic upgrade head`，从 `0001_baseline` 连续升级到 `0018_meeting_audio`，无错误。
- 核验新增表：
  - `meeting_audio`
  - `knowledge_documents`
  - `knowledge_chunks`
  - `user_memories`
  - `user_model_configs.llm_purpose_models`
  - `meeting_minutes.template` / `source_material_ids`
  - `meeting_records.marker_type`
- 验收后临时库已删除，未污染开发库。

## 四、真实 HTTP 闭环

使用隔离账号在最新后端 + 真实 PostgreSQL + 真实模型服务上执行：

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

临时库持久化计数：

| 表 | 行数 |
| --- | ---: |
| users | 1 |
| meetings | 1 |
| meeting_materials | 1 |
| document_chunks | 1 |
| knowledge_documents | 1 |
| knowledge_chunks | 1 |
| meeting_minutes | 1 |
| meeting_audio | 1 |
| user_memories | 1 |

## 五、未执行 / BLOCKED

| 项目 | 状态 | 原因 |
| --- | --- | --- |
| 真实 ASR 转写 | BLOCKED | 当前环境未配置 ASR Key；已用 Mock 与未配置失败路径覆盖 |
| 浏览器 Chromium E2E | SKIPPED | 项目未引入 Playwright/浏览器自动化；本地工作区目录授权无法在 jsdom 中真实验证 |
| 本地目录真实读写 | SKIPPED | 需要人工在支持 File System Access API 的 Chromium 浏览器验证 |
| 生产部署 | SKIPPED | 本次验收基线为 `develop`，未执行 `develop → main` 发布 |
| 实时流式 ASR | SKIPPED | 不在当前产品范围 |

## 六、验收结论

| 维度 | 结论 |
| --- | --- |
| 核心会议闭环（资料、准备、记录、问答、纪要、行动项、任务、问题） | PASS（真实 API + 真实数据库 + 真实 LLM/Embedding） |
| 记录标记、纪要模板、按用途模型、知识库、记忆中心 | PASS（自动化 + 真实 HTTP 闭环） |
| PostgreSQL 迁移 0013–0018 | PASS |
| 音频导入与失败/重试路径 | PASS（Mock；真实 ASR BLOCKED） |
| 前端构建与组件测试 | PASS |
| 浏览器端到端与本地目录授权 | SKIPPED（需人工/浏览器环境） |

**结论：核心 API、数据库和 AI 闭环达到可演示状态；音频真实转写、浏览器 E2E 与本地目录授权仍需在具备外部条件的环境中补验。不得把本报告中的 SKIPPED/BLOCKED 项表述为已通过。**

## 七、复验命令

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

# 数据库（示例：全新临时库）
$env:DATABASE_URL='postgresql+psycopg://openmind:change-me@localhost:5432/openmind_acceptance'
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
```
