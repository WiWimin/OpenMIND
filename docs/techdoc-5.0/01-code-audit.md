# 01 代码审计（code-audit）

> 基线：`main` @ `ff42641`（2026-11-01）；审计日期：2026-11-02。仅依据当前代码/配置，不沿用 4.1 统计。

## 一、技术栈与版本（以当前依赖与运行环境为准）

| 层 | 技术 | 版本 |
| --- | --- | --- |
| 前端 | Vue / Vite / TypeScript / Pinia / vue-router | 3.5.43 / 5.4.21 / 5.6.3 / 2.3.1 / 4.6.4 |
| 前端工具 | axios / Vitest / Playwright / Node | 1.20.0 / 2.1.9 / 1.64.1 / v22.23.2 |
| 后端 | FastAPI / SQLAlchemy / Pydantic / uvicorn | 0.150.0 / 2.1.5 / 2.14.1 / 0.54.0 |
| 后端工具 | httpx / Alembic / PyJWT / cryptography / Python | 0.28.1 / 1.20.0 / 2.15.1 / 50.0.2 / 3.13.16 |
| 数据库 | PostgreSQL 16 + pgvector（迁移用 Alembic） | — |
| AI | OpenAI 兼容（`/chat/completions`、`/embeddings`、`/audio/transcriptions`、`/models`） | — |
| 转写 | 本地 FunASR（funasr-server/sensevoice/CPU）或外部兼容 ASR | — |

`requirements.txt` 为范围约束（`fastapi>=0.115` 等），上表版本取自运行容器内实际安装。

## 二、统计口径与结果

| 项 | 数值 | 口径 |
| --- | --- | --- |
| API Router 模块 | 16 | `backend/app/api/v1/` 排除 `__init__.py`、`router.py`（含 `health`） |
| HTTP 路由装饰器 | 76 | GET 25 / POST 30 / PATCH 9 / PUT 3 / DELETE 9；另有 `main.py` `GET /health` → 合计 77 |
| ORM 表 | 16 | `backend/app/models/*.py` 的 `__tablename__` |
| 数据库迁移 | 22 | `backend/alembic/versions/`，head = `0022_audio_segments`，无 merge |
| services / repositories | 16 / 16 | 排除 `__init__.py` |
| 后端测试文件 | 36 | `backend/tests/**/test_*.py` |
| 前端测试文件 | 87 | `frontend/tests/**/*.spec.ts` |
| E2E spec / case | 5 / 7 | `frontend/e2e/*.spec.ts` |

ORM 表（16）：`users`、`meetings`、`meeting_materials`、`document_chunks`、`meeting_records`、`preparations`、`meeting_minutes`、`action_items`、`personal_tasks`、`open_issues`、`meeting_audio`、`meeting_templates`、`user_model_configs`、`knowledge_documents`、`knowledge_chunks`、`user_memories`。

迁移 0020–0022 的关键变化：
- `0020_drop_user_embedding_config`：删除 `user_model_configs` 的 `embedding_api_base/api_key_enc/model/dim` → **Embedding 收归服务端统一配置**。
- `0021_template_category_default`：`meeting_templates` 增加 `category`；`file_name`/`storage_key` 改为可空（支持仅文本的自定义模板）；`user_memories.preferred_minutes_template` 由 20 扩到 64（可引用内置/自定义模板 id）。
- `0022_audio_segments`：`meeting_audio` 增加 `segments`（JSONB）。

## 三、业务模块审计

| # | 模块 | 前端 | 后端 API | Service | 数据模型 | 状态 | 测试 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 用户认证 | `views/auth/*`、`stores/auth` | `api/v1/auth.py` | `auth_service` | `users`(active) | — | `test_auth` | 已实现；Mock 测试 |
| 2 | 会议管理 | `views/meetings/*` | `api/v1/meetings.py` | `meeting_service` | `meetings`(scheduled→archived) | 归档只读 | `test_meetings` | 已实现 |
| 3 | 材料上传/解析 | `components/Material*` | `api/v1/materials.py` | `material_service` | `meeting_materials`+`document_chunks` | uploaded→processing→processed/failed | `test_materials` | 已实现；Mock 测试 |
| 4 | 记录 | `components/RecordSection` | `api/v1/records.py` | `record_service` | `meeting_records` | — | `test_records` | 已实现 |
| 5 | 会前准备 | `PreprocessView`、`PreparationSection` | `api/v1/preparations.py` | `preparation_service` | `preparations`(draft→confirmed) | — | `test_preparations` | 已实现 |
| 6 | 会议问答 | `AgentChat`、`ChatPanel` | `api/v1/ai_chat.py` | `ai_chat_service`+`ai/chat` | — | — | `test_ai_chat` | 已实现；Mock 测试 |
| 7 | 纪要 | `MinutesSection`、`MinutesGenerateView` | `api/v1/minutes.py` | `minutes_service` | `meeting_minutes`(draft→confirmed) | — | `test_minutes` | 已实现 |
| 8 | 行动项 | `ActionItemSection` | `api/v1/action_items.py` | `action_item_service` | `action_items`(pending_confirmation→confirmed→converted) | 转任务幂等 | `test_action_items` | 已实现；Mock 测试 |
| 9 | 个人任务 | `TasksView`、`TaskSection` | `api/v1/tasks.py` | `task_service` | `personal_tasks`(todo→in_progress→completed；→cancelled) | 转换表硬约束 | `test_tasks` | 已实现 |
| 10 | 未解决问题 | `IssuesSection` | `api/v1/issues.py` | `issue_service` | `open_issues`(open→resolved/cancelled) | — | `test_issues` | 已实现 |
| 11 | 会议模板 | `TemplateManageView`、`TemplatePickerPopover` | `api/v1/templates.py` | `meeting_template_service` | `meeting_templates`(+category) | 内置 5 + 自定义 | `test_meeting_templates` | 已实现 |
| 12 | 个人知识库 | `KnowledgeUploader`、`settings/KnowledgeDialog` | `api/v1/knowledge.py` | `knowledge_service` | `knowledge_documents`+`knowledge_chunks` | uploaded→processing→processed/failed | `test_knowledge` | 已实现 |
| 13 | 用户记忆 | `settings/MemoryDialog` | `api/v1/memory.py` | `memory_service` | `user_memories` | — | `test_memory` | 已实现 |
| 14 | 模型配置 | `ModelPickerPopover`、`settings/ModelConfigDialog` | `api/v1/settings.py` | `model_config_service` | `user_model_configs`(仅 LLM) | — | `test_model_settings` | 已实现；Mock 测试 |
| 15 | 音频 | `AsrView`、`AudioSection`、`TranscriptStream`、`useLiveRecording` | `api/v1/audio.py` | `audio_service` | `meeting_audio`(+segments) | 见下 | `test_audio` | 已实现；部分 Mock 测试 |
| 16 | 健康检查 | — | `api/v1/health.py` + `main.py` | — | — | — | `test_health` | 已实现 |

## 四、音频能力专项审计（5.0 重点）

端点（`api/v1/audio.py`，共 12 个）：
- 上传/列表/详情：`POST /meetings/{id}/audio`、`GET /meetings/{id}/audio`、`GET /audio/{id}`。
- 实时分片：`POST /meetings/{id}/audio/live/start`、`POST /audio/{id}/live/chunk`（`seq`、`offset_seconds`）、`POST /audio/{id}/live/finish`。
- 分段：`POST /audio/{id}/segments/{seq}/retry`、`PATCH /audio/{id}/segments/marker`。
- 转写编辑/重试/确认/删除：`PATCH /audio/{id}`、`POST /audio/{id}/retry`、`POST /audio/{id}/confirm`、`DELETE /audio/{id}`。

实现事实（`services/audio_service.py`、`models/audio.py`）：
- 状态机：`uploaded → processing → transcribed / failed → confirmed`。
- 分片存储：`audio/{audio_id}/chunks/{seq:04d}.{ext}`；结束后按序合并为 `audio/{audio_id}.{ext}`，删除分片与临时目录（`storage.remove_tree`）。
- 分段结构（JSONB）：`[{seq, offset_seconds, text, marker_type, error}]`；`seq` 必须连续（不连续返回 422）。
- **边录边转**：每个分片上传后立即调用转写；单片失败仅记录 `error`，不中断整体（`append_live_chunk`）。
- 分片重试：仅 `processing` 会话内、分片文件仍在时可用（`retry_live_segment`）。
- 标记：`marker_type` 取值来自 `RecordMarkerType`（重点/决议/疑问），`set_segment_marker` 校验。
- 结束：合并分片，若全文非空 → `transcribed`，否则 `failed("实时转写失败，未得到任何文本")`；幂等（非 processing 直接返回）。
- 编辑转写：`update_transcript` 按行重拆分段（沿用相对时间与标记），状态置 `transcribed`。
- 确认：要求 `transcribed` 且有文本 → 创建 `RecordType.transcript` 的会议记录，`record_id` 回填，状态 `confirmed`；幂等（已有 record_id 直接返回）。
- 删除：若已确认（有 record_id）→ 409；否则删文件与分片、删记录。
- 异常与权限：越权 404；非会话/已确认的写操作 409；类型/大小校验（mp3/wav/m4a/webm，≤20MB）。
- **非流式**：分片边录边转是"分块上传 + 逐片转写"，不是 WebSocket/SSE 流式；需在文中如实区分。

未验证：真实 ASR 链路、真实浏览器录音、分片失败重试的真机验证（本次无 ASR/凭据）。

## 五、AI 与 RAG 专项审计

- **LLM**：`ai/llm/client.py`，OpenAI 兼容；`chat`/`chat_json`；新增 `probe()`（保存前连通性校验）与 `list_models()`（`GET /models`）。
- **Embedding**：`ai/embeddings/client.py`，维度 1024、批量 ≤16、超时 30s、3 次尝试；**仅服务端配置**（`docker/.env` 的 `EMBEDDING_*`），用户不可自备（`resolve_model_config` 直接取 `settings.embedding_*`）。
- **BYOK**：`user_model_configs` 仅 LLM 字段；密钥 Fernet 加密、掩码回传；保存前 `validate_api_base` + `_probe_llm`（429 限流时放行并返回 `llm_probe_verified=false`）。
- **用途模型**：`llm_purpose_models` 四用途（preparation/chat/minutes/extraction），**仅覆盖模型名**，不改变 api_base/key。
- **请求级覆盖**：`model_override` 直接覆盖模型名（不再校验"已登记列表"，有效性交由服务商判定）。
- **全局回退**：`ALLOW_GLOBAL_FALLBACK=false` 默认；且**只作用于 LLM**，Embedding 始终服务端配置。
- **Prompt/结构化输出**：`ai/prompts/`（chat/prepare/minutes/organize/extract_*）；`chat_json` 用 Pydantic 校验；整理链 summary/polish 输出 JSON（`_parse_structured` 容错剥离代码块）。
- **解析/切分**：`ai/parsers/`（pdf/docx/txt），`ai/indexing/chunker.py`（chunk 800 / overlap 120）。
- **检索**：`ai/rag/retriever.py` 双来源——材料 `document_chunks→meeting_materials→meetings` 过滤 `meetings.user_id`（当前会议再加 `meeting_materials.meeting_id`）；知识库 `knowledge_chunks→knowledge_documents` 过滤 `knowledge_documents.user_id`。
- **相似度**：应用层 Python 余弦（`ai/rag/similarity.py`），**非 pgvector 原生 ANN**；`top_k=5`、`min_score=0.3`。
- **记录/记忆**：会议记录不入向量索引，经 `_recent_record_context`（≤20 条 / 8000 字）作为直接上下文；用户记忆经 `memory_context_for(..., "chat")` 注入。
- **证据不足**：无片段且无记录 → 返回"证据不足"，不编造。
- **韧性**：超时/重试/错误分类（`MODEL_TIMEOUT/RATE_LIMITED/INTERNAL_ERROR/MODEL_CONFIG_INVALID/MODEL_QUOTA_EXCEEDED/MODEL_CONFIG_REQUIRED/MODEL_OUTPUT_INVALID`）；上游 5xx 映射为受控 500。

## 六、数据库与 API 设计一致性

- 用户隔离：会议/材料/记录/任务/问题/知识库/记忆按 `user_id` 过滤，越权 404。
- 文件与数据库一致性：上传失败回滚删除文件；音频分片合并后清理临时文件；确认音频生成记录并回填 `record_id`。
- 状态机（后端强制）：见第三节；会议 archived 写 409；任务/问题转换表硬约束。

## 七、前端结构

12 个视图、53 个组件、17 个 API 模块。5.0 新增：`TranscriptStream.vue`、`PolishDiffPanel.vue`、`SummaryCard.vue`、`ModePicker.vue`、`useLiveRecording.ts`、`settings/{ModelConfigDialog,TemplateFormDialog,KnowledgeDialog,MemoryDialog}.vue`、`constants/modelProviders.ts`、`types/{agent,audio,modelConfig,template}.ts`。

## 八、实现状态口径（用于 5.0 正文，必须区分）

| 标签 | 含义 | 本基线情况 |
| --- | --- | --- |
| 已实现 | 代码存在（路由 / service / model） | 16 模块均在代码中 |
| 已测试（Mock/单元） | 有自动化测试覆盖，但为 SQLite 内存库 + Mock Embedding / Mock HTTP，**非真实服务** | 后端 350、前端 447（详见 04） |
| 真实环境已验证 | 真实 PostgreSQL + 真实 LLM/Embedding/ASR + 浏览器真机验收 | **本次均未执行** |
| 未验证 | 无运行证据 | 真实 AI/ASR、实时录音分片链路、E2E、本地工作区、RAG 质量与性能 |
| 规划中 | 仓库无实现 | Nginx/TLS、多 worker、监控/备份、pgvector ANN、限流/异步队列/缓存 |

> 正文中"已实现"仅表示代码存在，**不代表通过真实环境验收**；不得把模块统一表述为"已验证"。模块表中"功能实现"列仅指代码存在，测试覆盖另见 04。
