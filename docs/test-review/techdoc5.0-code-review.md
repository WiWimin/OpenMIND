# OpenMIND 技术文档 5.0 代码一致性审查

> 审查对象：`docs/techdoc-5.0/OpenMIND-技术文档-5.0.docx`（与同名 `.md` 同源生成）。
> 审查方式：以当前 GitHub 远端 `main` 对应代码逐章核对，并重新执行自动化测试。
> 结论性质：**审查与测试复核，不构成第四阶段完成或项目最终验收通过。**

## 一、基线（第一阶段）

| 项 | 值 |
| --- | --- |
| 本地分支 | `main` |
| 本地 HEAD | `ff426413ef239e7f23133de206c402cab0b1d2a6` |
| `origin/main` | `ff426413ef239e7f23133de206c402cab0b1d2a6`（与 HEAD 相同） |
| `origin/develop` | `7454a2025429656211b756f761a6eb4d6848f88d` |
| 远端 | `https://github.com/WiWimin/OpenMIND.git` |
| README 所称 `main @ 332605e` | 实际为 `332605e642cd02583f2b9f47b7c06fbd4ba20af6`（2026-10-27），是当前 HEAD 的祖先，**不是当前 main** |

- 当前工作区业务代码与 HEAD 一致（`git status --porcelain -- backend/app frontend/src` 为空）；未提交修改仅为测试代码与文档/测试基础设施，已原样保留。
- 未执行切分支、reset、rebase、merge；测试直接针对 `origin/main` 对应业务代码（`ff42641`）。
- README 的 `332605e` 属过期引用；文档正文基线 `ff42641` 正确。

## 二、结论摘要

- 文档的统计口径、AI 参数、BYOK/SSRF、RAG 过滤、音频状态机等**关键描述与代码一致**。
- 未发现“把 Mock 写成真实供应商”的新增错误；B 组（队友）数据在文档中已标注为“依据队友报告记录”。
- 本次复核实际执行：后端 350、前端 449×5、PG 13/13、AI 22/22、音频 17/17、安全 14/14、SSRF 6/6、Fallback 4/4、E2E 8/8×3，全部通过。
- 发现并修复测试代码问题 1 项（条件 `test.skip`）、补齐 E2E 缺口 2 项（登录、纪要生成）。
- 文档需修订：E2E 数量（6→8，若保留新增用例）、B 组数据可复核性说明、README 基线过期。

## 三、逐章审查

### 1. 项目概述与技术栈

| 文档项 | 代码/环境实测 | 结论 |
| --- | --- | --- |
| Vue / Vite / TS / Pinia / vue-router | 3.5.43 / 5.4.21 / 5.6.3 / 2.3.1 / 4.6.4（前端容器 `npm ls`） | 一致 |
| FastAPI / SQLAlchemy / Pydantic / uvicorn | 0.150.0 / 2.1.5 / 2.14.1 / 0.54.0（后端容器） | 一致 |
| Python / Node | 3.13.16 / v22.23.2（容器内） | 一致；文档已注明“容器内” |
| PostgreSQL / pgvector | 16.15 / 0.8.7（测试库） | 一致 |
| 存储与限制 | `storage_dir=./storage`；PDF/DOCX/TXT；单文件 ≤20MB | 一致 |

### 2. 需求与功能模块

16 个后端模块与前端页面均存在（认证、会议 CRUD/归档、材料、准备、记录、问答、纪要、行动项、任务、问题、模板、知识库、记忆、模型配置、音频、健康检查）。**存在路由/页面不等于已验证**；本轮测试覆盖情况见 `test-execution-report.md`。

### 3. 系统架构与统计

| 统计项 | 实测 | 口径 | 文档 |
| --- | --- | --- | --- |
| API Router | 16 | `backend/app/api/v1/*.py` 排除 `__init__.py`、`router.py` | 16 |
| HTTP 端点 | 77 | 76 个 `@router.*`（GET 25 / POST 30 / PUT 3 / PATCH 9 / DELETE 9）+ `main.py` `/health` | 77 |
| ORM 表 | 16 | `backend/app/models/*.py` 的 `__tablename__` | 16 |
| 迁移 | 22，head `0022_audio_segments` | `backend/alembic/versions/` | 一致 |
| services / repositories | 16 / 16 | 排除 `__init__.py` | 一致 |
| 音频接口 | 12 | `backend/app/api/v1/audio.py` | 12 |
| 内置模板 | 6 | `meeting_template_service.BUILTIN_TEMPLATES` | 6 |
| 前端页面 | 12 个 `.vue`（views） | `frontend/src/views/` | 文档未单列 |

### 4. AI 技术方案

| 项 | 代码证据 | 结论 |
| --- | --- | --- |
| LLM 温度/超时/重试 | `ai/llm/client.py`：0.2、60s、3 次、退避 1s/3s | 一致 |
| Embedding | 1024 维、批量 ≤16、超时 30s（`ai/embeddings/client.py`） | 一致 |
| RAG 权限 | `ai/rag/retriever.py`：`Meeting.user_id` + `meeting_materials.meeting_id`；知识库 `knowledge_documents.user_id` | 一致 |
| scope | `current_meeting` / `knowledge_base` | 一致 |
| Top-K / 阈值 | `top_k=5`、`min_score=0.3` | 一致 |
| 分块 | 800 / overlap 120（`indexing_service.py`） | 一致 |
| 记录上下文 | `_recent_record_context(limit=20, char_limit=8000)` | 一致 |
| BYOK | `app/core/crypto.py`：MultiFernet（`SECRET_KEY` SHA-256 + `SECRET_KEY_PREVIOUS`）、掩码回传 | 一致 |
| Fallback | `allow_global_fallback=False` 默认，仅作用 LLM | 一致 |
| SSRF | `allow_private_model_endpoints=False` 默认；探测/保存均校验 | 一致 |
| 429 探测容错 | `RATE_LIMITED` 放行并标记 `llm_probe_verified=false` | 一致 |

### 5. 音频与本地工作区

| 项 | 代码证据 | 结论 |
| --- | --- | --- |
| 音频类型/大小 | `mp3/wav/m4a/webm`，≤20MB | 一致 |
| 状态机 | `uploaded→processing→transcribed/failed→confirmed` | 一致 |
| 分片 | `audio/{id}/chunks/{seq}.ext`、`live/start|chunk|finish`、非 WS/SSE | 一致 |
| 分段 | JSONB `seq/offset_seconds/text/marker_type/error` | 一致（模型与迁移） |
| 重试/合并/确认 | `retry`、finish 合并清理、confirm 生成 `RecordType.transcript` | 一致 |
| 删除限制 | 已确认（有 `record_id`）不可删 | 一致 |
| 本地工作区 | `showDirectoryPicker` + `requestPermission` + IndexedDB | 一致；真实写入未验收 |

### 6. 创新点

第 6 章保留独立成章；6.1/6.2 的“问题—机制—位置—价值—验证/局限”结构与代码位置一致（`ai/rag/retriever.py`、`model_config_service.py`、`action_item_service.py`、`audio_service.py`、`ai/chat/service.py`）。

### 7. 测试与部署

- 7.2 表 7-1（A 组 `ff42641`）的数字本轮已复现（详见测试报告）；文档“449 连续 5 次”“E2E 6/6×3”成立。
- 表 7-2（B 组 `e38fe2a`）**无法在本仓库复核**：该提交不在本地/远端历史，原始日志未提供；文档已标注“依据队友报告记录”。
- 7.3 未验收项与实测边界一致；真实 LLM/Embedding/ASR 在本环境仍为 BLOCKED。
- 7.4 部署描述与 `docker/compose.dev.yml` 一致。

### 8. 总结与展望

指标表与代码统计一致；B 组数据已单列，未与 A 组合并。

## 四、文档与代码不一致清单

| ID | 文档/材料表述 | 实际 | 级别 | 处理建议 |
| --- | --- | --- | --- | --- |
| D1 | README：`main @ 332605e` | 当前 `origin/main=ff42641`；332605e 为 10-27 祖先提交 | 低 | 更新 README 基线与日期 |
| D2 | 表 7-2 B 组数据（`e38fe2a`） | 该提交不在本仓库；数据仅见队友报告 | 中 | 保留“依据报告记录”字样；补充队友提交/日志链接 |
| D3 | E2E “6 spec / 6 case” | 审查前仓库确为 6/6；本次补充登录、纪要 2 条后为 8/8 | 低 | 若保留新增用例，文档改为 8/8；否则注明 6 条为审查前基线 |
| D4 | 7.2.1 “B 组清理提交删除 1 后端/11 前端用例” | 无法在本仓库验证 | 中 | 同 D2，保持来源标注，勿写成已复核 |
| D5 | B 组真实 FunASR/GLM 成功 | 本环境无真实凭据、无 FunASR 镜像，无法复测 | 中 | 保持“依据报告记录”；不得表述为本环境已验证 |
| D6 | pytest 115.49s | 本轮 98.94s（机器负载差异） | 信息 | 无需修改；耗时非固定指标 |
| D7 | 文档称“测试证据文件均存在” | `04/05/06` 与 `test-logs/` 均存在 | 无 | 保持 |

> 说明：D2/D4/D5 均已在文档中标注来源；本次未发现“把 Mock 当真实”“把 skipped 当 passed”的新增表述。

## 五、推荐修订清单（不直接改 DOCX/PDF）

1. 更新 README 的 `main @ 332605e` 为当前 `ff42641`（完整 SHA）。
2. 若保留本次新增 E2E：§7.2 表 7-1 的 E2E 改为 8 spec / 8 case（并注明其中 2 条为审查补充）；否则保留 6/6 但注明“审查前基线”。
3. 表 7-2 与附录 D 的 B 组条目补充“无法在本仓库复核”的说明，避免读者误认为已独立复测。
4. 保持真实 LLM/Embedding/ASR 的 BLOCKED/NOT RUN 标注，不新增“已通过”表述。
5. 其余统计与参数无需修改。

## 六、修订落地（2026-11-03）

- README 基线已由 `332605e` 更新为 `ff42641`。
- 技术文档 §7.2 表 7-1、§7.2.3、表 7-3、§8.1、附录 A/D 的 E2E 口径已由 6/6 更新为 **8/8（6 条既有 + 2 条审查补充）**。
- 表 7-2、§7.2、附录 D 的 B 组条目已补充“该提交不在本仓库/远端历史，无法独立复核”。
- 历史 `04/05/06` 报告未覆盖；本次复核记录保留在 `docs/test-review/`。
