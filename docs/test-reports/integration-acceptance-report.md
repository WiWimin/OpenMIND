# OpenMIND 集成测试与业务闭环验收报告

> 生成时间：2026-10-17
> 执行范围：真实 Docker 环境（PostgreSQL/pgvector + FastAPI + Vue 前端）下的集成测试与业务闭环验收。
> 结论口径：仅在存在实际证据时标记 PASS；受外部配额/权限限制的标记 BLOCKED；未执行的标记 SKIPPED。

## 一、环境信息

| 项 | 值 |
| --- | --- |
| 宿主机 | Windows + Docker Desktop |
| 后端 | Python 3.13 + FastAPI（uvicorn），容器 `openmind-backend-1`，端口 `127.0.0.1:8001→8000` |
| 数据库 | PostgreSQL 16 + pgvector，容器 `openmind-db-1`，端口 `127.0.0.1:5432`（healthy） |
| 前端 | Vue 3 + Vite（dev server），容器 `openmind-frontend-1`，端口 `0.0.0.0:5173` |
| 迁移 | Alembic `head = 0012_user_model_configs`（已应用） |
| pgvector 版本 | `vector 0.8.7` |
| 大模型 | DeepSeek `deepseek-flash`（可用） |
| Embedding | 阿里百炼 `text-embedding-v3`（1024 维，**免费额度耗尽**） |

> 说明：同一 Docker 主机上另有其他项目容器（`question-bank-*`、`pet-*`、`test02-*`），本次未触碰。

## 二、关键执行命令

```bash
# 迁移（补齐业务表 0003–0012）
docker exec openmind-backend-1 alembic upgrade head

# 后端镜像无缓存重建（修复缺失 cryptography/PyJWT）
docker compose -f docker/compose.dev.yml -f docker/compose.local.yml build --no-cache backend
docker compose -f docker/compose.dev.yml -f docker/compose.local.yml up -d backend

# 前端依赖补齐（修复缺失 @tiptap/*、docx）
docker exec openmind-frontend-1 npm install

# 全量自动化测试
docker exec openmind-backend-1 sh -c "ruff check . && pytest"
docker exec openmind-frontend-1 sh -c "npm run typecheck && npm run lint && npm run test -- --run && npm run build"

# 连通性自检
docker exec openmind-backend-1 python scripts/check_ai.py
```

## 三、全量自动化测试（复跑，SQLite/单元）

| 项 | 结果 |
| --- | --- |
| 后端 `ruff check .` | PASS（All checks passed） |
| 后端 `pytest` | PASS（193 项全部通过） |
| 前端 `npm run typecheck` | PASS |
| 前端 `npm run lint` | PASS |
| 前端 `npm run test -- --run` | PASS（309 项通过，64 文件） |
| 前端 `npm run build` | PASS（`✓ built in 9.91s`） |

> 注：以上自动化测试主要跑在 SQLite 内存库，不等同于真实 PostgreSQL/pgvector 验证（见下节单独验证）。

## 四、PostgreSQL / pgvector 单独验证（真实库）

| # | 检查项 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | pgvector 扩展 | PASS | `SELECT extname,extversion → vector 0.8.7` |
| 2 | `document_chunks.embedding` 类型 | PASS | `vector(1024)`，索引/唯一约束/FK 齐全 |
| 3 | 向量写入 + 读取 | PASS | 真实表 INSERT 成功，`vector_dims=1024` |
| 4 | 余弦距离算子 `<=>` | PASS | 同向向量相似度 `1.0000`，正交向量 `0.0000` |
| 5 | 维度约束 | PASS | 写入 3 维被拒：`expected 1024 dimensions, not 3` |
| 6 | 数据清理 | PASS | 事务回滚/删除后 `count=0`，无残留 |

## 五、模型服务配置与配额

| 服务 | 状态 | 说明 |
| --- | --- | --- |
| LLM（deepseek-flash） | **PASS** | 实测 `check_ai.py` 返回「正常」，637ms |
| Embedding（text-embedding-v3） | **BLOCKED** | 免费额度耗尽：`Free quota exhausted ... AllocationQuota.FreeTierOnly` |

> BLOCKED 解除条件：阿里百炼充值或关闭「仅免费额度」；或用户在模型设置页配置自有 1024 维 embedding key（BYOK）。

## 六、业务闭环验收（隔离账号 + 真实 PostgreSQL 持久化）

账号 `itest_<ts>`，测试后已清理。结果：

| # | 步骤 | 结果 | 说明 |
| --- | --- | --- | --- |
| 1 | 注册 | PASS | HTTP 201 |
| 2 | 创建会议 | PASS | HTTP 201 |
| 3 | 上传资料 | **BLOCKED** | 解析成功，索引因 embedding 额度 `processing_status=failed`（优雅降级，非 500） |
| 4 | 创建记录 | PASS | HTTP 201 |
| 5 | 会前准备（LLM） | PASS | HTTP 200 |
| 6 | 问答（RAG） | **BLOCKED** | 无分块可检索 → 走 `insufficient_evidence=true` 证据不足路径（正确兜底） |
| 7 | 生成纪要（LLM） | PASS | HTTP 201 |
| 8 | 行动项提取（LLM） | PASS | 提取 3 条 |
| 9 | 问题提取（LLM） | PASS | HTTP 200 |
| 10a | 确认行动项 | PASS | HTTP 200 |
| 10b | 行动项转任务 | PASS | 生成 `task_id` |
| 10c | 任务→进行中 | PASS | HTTP 200 |
| 10d | 任务→完成 | PASS | HTTP 200 |
| 11 | 模型配置读取（BYOK 脱敏） | PASS | 返回 `llm_model=deepseek-flash`，密钥脱敏 |

**数据库持久化验证**（真实 PostgreSQL，按表计数）：

| 表 | 行数 | 表 | 行数 |
| --- | --- | --- | --- |
| users | 1 | minutes | 1 |
| meetings | 1 | action_items | 3 |
| materials | 1 | open_issues | 1 |
| chunks | 0（索引 BLOCKED） | personal_tasks | 1（completed） |
| records | 1 | preparations | 1 |

状态核对：`personal_tasks.status=completed`、`action_items.status`（1 converted + 2 pending_confirmation）——与「确认→转任务→状态流转」一致。

## 七、负面测试（16 项）

| # | 场景 | 期望 | 实际 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 未登录 GET /meetings | 401 | 401 | PASS |
| 2 | 未登录 POST /meetings | 401 | 401 | PASS |
| 3 | 注册新账号 | 201 | 201 | PASS |
| 4 | 重名注册 | 422/409 | 409 `BUSINESS_RULE_VIOLATION` | PASS（api.md 允许 422 或 409） |
| 5 | 建会 | 201 | 201 | PASS |
| 6 | 建记录 | 201 | 201 | PASS |
| 7 | 无效文件类型 .exe | 415 | 415 `FILE_TYPE_NOT_SUPPORTED` | PASS |
| 8 | 越权：B 读 A 会议 | 404 | 404 | PASS |
| 9 | 越权：B 改 A 记录 | 404 | 404 | PASS |
| 10 | 行动项未确认转任务 | 409 | 409 | PASS |
| 11 | 确认后转任务 | 201 | 201 | PASS |
| 12 | 完成任务后 reopen | 409 | 409 | PASS |
| 13 | 完成任务后 cancel | 409 | 409 | PASS |
| 14 | 有已转任务删会议 | 409 | 409 | PASS |
| 15 | 不存在会议 | 404 | 404 | PASS |
| 16 | BYOK 无效密钥（probe 拒绝） | 400 | 400 `MODEL_CONFIG_INVALID` | PASS |

## 八、前端浏览器验收（Playwright + Chromium）

| 检查 | 结果 |
| --- | --- |
| 根路径重定向到登录页 | PASS（`/` → `/login`） |
| 登录页渲染（`#login-name`、`#login-password`） | PASS |
| 登录后落点 | PASS（`/dashboard` 正常渲染，含「会议列表 / 模型设置 / AI 会议个人助理」导航） |
| 截图证据 | `ui_login.png`、`ui_dashboard.png`（本地临时目录） |

> 完整 UI 手工验收（各功能模块点选、视觉还原度）仍建议人工复核；本次仅验证核心页面可达与登录闭环。

## 九、发现的问题（本次未改动代码）

| # | 问题 | 级别 | 处理建议 |
| --- | --- | --- | --- |
| 1 | 前端容器端口仍为 `0.0.0.0:5173`（compose 已改 127.0.0.1，但容器未重建） | 低 | `docker compose up -d frontend` 重建即可 |
| 2 | 登录落点实现为 `/dashboard`，`design-baseline.md D-19` 仍写 `/meetings` | 低（文档不一致） | 更新 D-19 或前端路由 |
| 3 | 重名注册返回 409，`api.md` 标注「422 或 409」，建议二选一定死 | 低（文档） | 统一文档口径 |

> 本次为纯验证，未发现需修改的代码缺陷；上述 3 项均为配置/文档层面，未做无关重构。

## 十、未验证事项

- RAG 语义检索端到端（受 embedding 额度 BLOCKED，未测到「分块命中→带来源回答」路径）
- 上传资料的 `processed` 成功态（索引需要 embedding）
- 前端各模块的完整人工视觉/交互验收
- 生产部署（`main` 分支发布、非 dev 环境）

## 十一、验收结论与建议

### 是否达到发布验收条件？

**部分达到，未完全达到。** 结论如下：

| 维度 | 结论 |
| --- | --- |
| 代码完整性（M00–M10） | ✅ 全部实现，全量自动化测试全绿 |
| 真实 PostgreSQL/pgvector | ✅ 单独验证通过 |
| 业务闭环（除 RAG 检索） | ✅ 真实环境走通，持久化正确 |
| 权限/异常/负面 | ✅ 16 项全部通过 |
| 前端核心页面 | ✅ 可达、登录闭环可用 |
| **RAG 语义检索** | ❌ **BLOCKED**（embedding 免费额度耗尽，外部原因） |

### 剩余风险

1. **RAG 语义检索未闭环**：唯一未验证的核心功能，阻塞原因是百炼免费额度耗尽（非代码缺陷）。解除后应补测「上传→索引→带来源问答」全链路。
2. **`main` 分支未发布**：当前验证基于 `develop`；正式交付需推进 `develop → main`。
3. **UI 手工验收待补**：浏览器自动化只验证了可达性与登录闭环，未覆盖全部交互。
4. **文档口径**：D-19 落点、重名错误码等 3 处文档不一致需收尾。

### 建议

1. 解除 embedding 额度限制（充值/关免费额度，或使用 BYOK 配自有 key）后，重跑第六节第 3、6 步，验证 RAG 闭环。
2. 完成 `develop → main` 发布后，在 `main` 上再跑一次本报告的核心步骤。
3. 补齐前端手工验收与文档口径统一。
