# 共享数据层设计

本文件是前后端、AI 后端共同遵循的数据契约。字段、关系、状态和数据归属在业务开发前需达成一致。

> 状态：MVP 设计基线。字段类型为 PostgreSQL 建议类型；未决事项见 [`design-baseline.md`](design-baseline.md)。

## 一、数据设计原则

1. 个人数据隔离：用户只能访问自己拥有的会议、资料、记录、任务和问题。
2. 全流程可追溯：AI 结果能够关联来源会议、材料或会议记录。
3. 原始数据与 AI 结果分离：保留用户原始记录，不以 AI 生成结果覆盖原文。
4. 候选与确认分离：AI 提取的行动项和纪要必须允许用户编辑、确认。
5. 独立更新：纪要、行动项和任务可以分别更新，历史确认任务不因纪要修改而丢失来源关联。
6. 业务状态由后端控制：前端不能通过直接修改状态字段绕过权限或业务规则。
7. 来源约束：所有下级实体（材料、记录、准备、纪要、行动项、问题）必须能追溯到所属会议；查询时先校验会议归属当前用户。

## 二、主键与通用字段约定

### 2.1 主键格式（已定）

所有主键由后端生成，采用**带前缀字符串 ID**，类型 `VARCHAR(40)`：

| 实体 | 前缀 | 字段 |
| --- | --- | --- |
| users | `usr_` | `user_id` |
| meetings | `mtg_` | `meeting_id` |
| meeting_materials | `mat_` | `material_id` |
| meeting_records | `rec_` | `record_id` |
| preparations | `prep_` | `preparation_id` |
| meeting_minutes | `min_` | `minutes_id` |
| action_items | `act_` | `action_id` |
| personal_tasks | `tsk_` | `task_id` |
| open_issues | `iss_` | `issue_id` |
| document_chunks | `chk_` | `chunk_id` |
| knowledge_documents | `kdoc_` | `document_id` |
| knowledge_chunks | `kchk_` | `chunk_id` |
| meeting_audio | `aud_` | `audio_id` |
| meeting_templates | `tpl_` | `template_id` |
| async_jobs | `job_` | `job_id` |
| ai_call_logs | `ail_` | `log_id` |

- 形如 `mtg_` + 32 位十六进制（如 `mtg_8f3a1c...`）。
- 外键字段必须与被引用主键类型一致（均 `VARCHAR(40)`）。
- 前端不得自行生成业务主键。

### 2.2 通用字段

- 时间：统一 `TIMESTAMPTZ`，以 **UTC** 存储；仅日期使用 `DATE`；`created_at`/`updated_at` 默认 `now()`，由后端维护。
- 结构化附加数据可用 `JSONB`，但核心状态和关联 ID 不藏在 JSON 中。
- 版本：`version` 从 1 开始，编辑后递增。
- 幂等键：可被外部重试创建的实体（`meeting_materials` / `meeting_records` / `action_items` / `open_issues` / `meeting_audio`）带 `client_op_id VARCHAR(64)`（可空）并建唯一索引；同一幂等键重复提交只落一条，内容不同返回 409 `IDEMPOTENCY_KEY_REUSED`（迁移 `0027_client_op_id`）。

## 三、核心数据实体

> `PK` 主键；`NN` 非空；`UQ` 唯一；`FK` 外键；`IDX` 索引；`?` 可空。

### 3.1 `users` 用户

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | VARCHAR(40) | PK | `usr_` 前缀 |
| `name` | VARCHAR(100) | NN, UQ | **唯一登录标识**（登录名兼显示名） |
| `password_hash` | TEXT | NN | 密码哈希，禁止明文 |
| `status` | VARCHAR(20) | NN, default `active` | `active` / `disabled` |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 登录标识为 `name`；**不设 email 字段**。
- 密码哈希算法由后端安全实现决定（成熟算法，禁止明文/可逆/普通 SHA）。
- API 不得返回 `password_hash`。

### 3.2 `meetings` 会议

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `meeting_id` | VARCHAR(40) | PK | `mtg_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户 |
| `title` | VARCHAR(200) | NN | 标题 |
| `topic` | TEXT | ? | 主题/背景 |
| `meeting_time` | TIMESTAMPTZ | ?, IDX | 计划时间 |
| `status` | VARCHAR(20) | NN, default `scheduled` | 见 §五 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |
| `archived_at` | TIMESTAMPTZ | ? | 归档时间 |

### 3.3 `meeting_materials` 会议材料

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `material_id` | VARCHAR(40) | PK | `mat_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户（便于过滤） |
| `file_name` | VARCHAR(255) | NN | 原始文件名 |
| `type` | VARCHAR(30) | NN | 标准化类型：`pdf` / `docx` / `txt` |
| `source` | VARCHAR(100) | ? | 来源说明 |
| `storage_key` | TEXT | NN | 存储定位键，不暴露前端 |
| `content` | TEXT | ? | 解析后文本（原文件独立存储） |
| `content_hash` | VARCHAR(64) | ? | 文件内容摘要（sha256 hex），增量索引同内容判定依据 |
| `index_fingerprint` | VARCHAR(64) | ? | 索引参数指纹；为空=产出参数未知，不得作为复用源 |
| `indexed_at` | TIMESTAMPTZ | ? | 最近一次成功建索引时间 |
| `processing_status` | VARCHAR(20) | NN, default `uploaded` | 见 §五 |
| `parse_error` | TEXT | ? | 内部安全错误摘要 |
| `parse_error_code` | VARCHAR(40) | ? | 失败错误码（`FILE_PARSE_FAILED` / `MODEL_CONFIG_REQUIRED` / `INTERNAL_ERROR` 等），供前端映射文案 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- `meeting_materials.user_id` 必须与会议所属用户一致。
- 支持扩展名当前为 `.pdf` / `.docx` / `.txt`（对齐解析层 `SUPPORTED_EXTENSIONS`）。
- 删除材料须由业务服务同步清理 `document_chunks` 与文件对象。
- **增量索引复用规则**（迁移 `0028_rag_content_hash`）：`user_id` + `content_hash` + `index_fingerprint` 三者一致、且 `processing_status='processed'` 的记录可作为复用源，把分块复制到新材料（新 `chunk_id`，内容与向量原样）。复用范围**仅限本表内**（可跨会议），不与 `knowledge_chunks` 互相复用，避免跨库脏召回。

### 3.4 `meeting_records` 会议记录

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `record_id` | VARCHAR(40) | PK | `rec_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `content` | TEXT | NN | 记录文本 |
| `record_type` | VARCHAR(20) | NN, default `manual` | `manual` / `transcript` / `imported` |
| `marker_type` | VARCHAR(20) | ? | `highlight` / `decision` / `question`；每条记录最多一个 |
| `source_material_id` | VARCHAR(40) | FK→meeting_materials, ? | 转写/导入来源 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

### 3.5 `preparations` 会前准备稿

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `preparation_id` | VARCHAR(40) | PK | `prep_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `summary` | TEXT | NN, default '' | 会前摘要 |
| `checklist` | JSONB | NN, default `[]` | 字符串数组 |
| `status` | VARCHAR(20) | NN, default `draft` | 见 §五 |
| `version` | INTEGER | NN, default 1 | |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 版本：每次**生成**新增记录；对同一条记录的**编辑**原地更新并 `version` 递增（`ai-design.md 八.1`）。

### 3.6 `meeting_minutes` 会议纪要

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `minutes_id` | VARCHAR(40) | PK | `min_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `content` | TEXT | NN | 纪要正文 |
| `status` | VARCHAR(20) | NN, default `draft` | 见 §五 |
| `version` | INTEGER | NN, default 1 | |
| `template` | VARCHAR(20) | NN, default `standard` | `standard` / `concise` / `task_list` / `custom`（套用会议模板清单时的标记） |
| `source_record_ids` | JSONB | NN, default `[]` | 生成依据的记录 ID 快照 |
| `source_material_ids` | JSONB | NN, default `[]` | 生成依据的材料 ID 快照 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 版本：每次**生成**新增记录；编辑原地更新并 `version` 递增，确认置 `confirmed`（`ai-design.md 八.4`）。

### 3.7 `action_items` 行动项

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `action_id` | VARCHAR(40) | PK | `act_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `content` | TEXT | NN | 行动内容 |
| `assignee` | VARCHAR(100) | ? | 负责人文本，不一定关联系统用户 |
| `due_date` | DATE | ? | 截止日期 |
| `status` | VARCHAR(30) | NN, default `pending_confirmation` | 见 §五 |
| `source_record_id` | VARCHAR(40) | FK→meeting_records, ? | 主要来源记录 |
| `source_excerpt` | TEXT | ? | 支撑原文片段 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- `meeting_id` 非空；删除其所属会议前须检查是否存在已转换行动项（见 §七）。

### 3.8 `personal_tasks` 个人任务

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `task_id` | VARCHAR(40) | PK | `tsk_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 任务所属用户 |
| `meeting_id` | VARCHAR(40) | FK→meetings, ?, IDX | 来源会议 |
| `action_id` | VARCHAR(40) | FK→action_items, ?, UQ | 来源行动项（唯一） |
| `title` | VARCHAR(255) | NN | 标题 |
| `status` | VARCHAR(20) | NN, default `todo` | 见 §五 |
| `priority` | VARCHAR(10) | NN, default `medium` | `high` / `medium` / `low`，CHECK 约束（迁移 0032） |
| `due_date` | DATE | ? | 截止日期 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- `action_id` 唯一：保证同一行动项不重复生成任务（转任务幂等）。
- 转换任务的 `user_id` 必须为当前用户，不接受请求体指定。

### 3.9 `open_issues` 待跟进问题

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `issue_id` | VARCHAR(40) | PK | `iss_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `description` | TEXT | NN | 问题描述 |
| `status` | VARCHAR(20) | NN, default `open` | 见 §五 |
| `follow_up` | TEXT | ? | 跟进内容 |
| `source_record_id` | VARCHAR(40) | FK→meeting_records, ? | 来源记录 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

### 3.10 `document_chunks` 文档分块

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `chunk_id` | VARCHAR(40) | PK | `chk_` 前缀 |
| `material_id` | VARCHAR(40) | FK→meeting_materials, NN, IDX | 来源材料 |
| `content` | TEXT | NN | 分块文本 |
| `chunk_index` | INTEGER | NN | 顺序，从 0 开始 |
| `embedding` | `vector(1024)` | ? | 维度固定 **1024** |
| `created_at` | TIMESTAMPTZ | NN, default now() | |

- 唯一约束：`UNIQUE(material_id, chunk_index)`。
- 嵌入模型：阿里百炼 `text-embedding-v3`，维度 1024（依据 M00-08 验证）。
- 未生成 embedding 的分块可为空；检索不得把空向量当有效向量。
- 删除/重新解析材料时清理旧分块。
- 向量索引：`ix_document_chunks_embedding_hnsw`（HNSW, `vector_cosine_ops`, m=16, ef_construction=64，迁移 `0029_rag_hnsw`）；排序下沉 PostgreSQL（`embedding <=> query`），权限过滤仍在 SQL 前置。

### 3.11 `user_model_configs` 用户模型配置

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | VARCHAR(40) | PK, FK→users | 每个用户一行 |
| `llm_api_base` | VARCHAR(255) | ? | LLM API 地址 |
| `llm_api_key_enc` | TEXT | ? | LLM 密钥 Fernet 密文 |
| `llm_model` | VARCHAR(100) | ? | 默认 LLM 模型 |
| `llm_purpose_models` | JSONB | NN, default `{}` | 用途→模型名覆盖 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 仅保存用户自备的 **LLM** 配置；向量模型（Embedding）收归服务端 `docker/.env` 统一配置，用户侧无对应字段（迁移 `0020_drop_user_embedding` 已删除原 embedding 四字段）。
- `llm_purpose_models` 仅保存允许用途：`preparation` / `chat` / `minutes` / `extraction`。
- 未覆盖的用途回退到 `llm_model`；API 地址与密钥统一使用 LLM 配置。
- 用途模型名最长 100 字符，空值不得保存。
- 删除用户模型配置时同时清除用途覆盖。

### 3.12 `knowledge_documents` 个人知识库文档

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `document_id` | VARCHAR(40) | PK | `kdoc_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户 |
| `file_name` | VARCHAR(255) | NN | 原始文件名 |
| `type` | VARCHAR(30) | NN | `pdf` / `docx` / `txt` |
| `storage_key` | TEXT | NN | 本地存储相对路径 |
| `content` | TEXT | ? | 解析文本 |
| `content_hash` | VARCHAR(64) | ? | 文件内容摘要（sha256 hex），增量索引同内容判定依据 |
| `index_fingerprint` | VARCHAR(64) | ? | 索引参数指纹；为空=产出参数未知，不得作为复用源 |
| `indexed_at` | TIMESTAMPTZ | ? | 最近一次成功建索引时间 |
| `processing_status` | VARCHAR(20) | NN, default `uploaded` | 见状态 |
| `parse_error` | TEXT | ? | 解析/索引失败原因 |
| `parse_error_code` | VARCHAR(40) | ? | 失败错误码，供前端映射文案 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- **增量索引复用规则**（迁移 `0028_rag_content_hash`）：与 `meeting_materials` 同构，复用范围**仅限本表内**（可跨文档），不与 `document_chunks` 互相复用。

### 3.13 `knowledge_chunks` 知识库分块

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `chunk_id` | VARCHAR(40) | PK | `kchk_` 前缀 |
| `document_id` | VARCHAR(40) | FK→knowledge_documents, NN, IDX | 来源文档 |
| `content` | TEXT | NN | 分块文本 |
| `chunk_index` | INTEGER | NN | 从 0 开始 |
| `embedding` | `vector(1024)` | ? | 维度固定 1024 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |

- 唯一约束：`UNIQUE(document_id, chunk_index)`。
- 删除文档时同步删除分块与向量索引。
- 知识库与会议资料使用独立表，检索范围不得自动混用。
- 向量索引：`ix_knowledge_chunks_embedding_hnsw`（HNSW, `vector_cosine_ops`, m=16, ef_construction=64，迁移 `0029_rag_hnsw`）。

### 3.14 `user_memories` 用户记忆

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | VARCHAR(40) | PK, FK→users | 每个用户最多一行 |
| `role` | VARCHAR(100) | ? | 职业/角色 |
| `work_scenarios` | TEXT | ? | 工作场景 |
| `communication_style` | TEXT | ? | 表达偏好 |
| `preferred_minutes_template` | VARCHAR(64) | ? | 内置枚举值（`standard` / `concise` / `task_list`）或自定义模板 ID |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 记忆由用户显式维护；不允许自动写入未确认的偏好。
- 删除记忆只删除该用户画像，不影响会议、纪要或任务数据。
- 用途筛选在服务层完成，不把全部记忆无条件注入所有 AI 任务。

### 3.15 `meeting_audio` 会议音频

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `audio_id` | VARCHAR(40) | PK | `aud_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户 |
| `file_name` | VARCHAR(255) | NN | 原始文件名 |
| `type` | VARCHAR(20) | NN | `mp3` / `wav` / `m4a` / `webm`（音频）或 `docx` / `txt`（已转写文稿） |
| `storage_key` | TEXT | NN | 本地存储相对路径 |
| `transcript` | TEXT | ? | 可编辑转写文本（实时分段按 `\n` 拼接） |
| `segments` | JSONB | ? | 转写分段：`[{seq, offset_seconds, text, marker_type, error}]`，`seq` 从 1 连续递增 |
| `status` | VARCHAR(20) | NN, default `uploaded` | 见状态 |
| `error` | TEXT | ? | 转写失败原因 |
| `record_id` | VARCHAR(40) | FK→meeting_records, ? | 确认后生成的记录 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 状态：`uploaded` / `processing` / `transcribed` / `failed` / `confirmed`；实时录音会话期间保持 `processing`，`live/finish` 后落定。
- `segments` 由后端维护：分片转写追加、全文修订后按行重拆（沿用原相对时间与标记）；`marker_type` 取值与记录标记一致（`highlight` / `decision` / `question`）。
- 确认后创建 `record_type=transcript` 的会议记录，并写入 `record_id`。
- 已确认音频不能重新转写或删除。
- 删除未确认音频时同步删除文件（含实时会话的分片文件）。

### 3.16 `meeting_templates` 会议模板

用户上传的自定义输出模板；内置模板由代码常量提供，不入库（`api.md 5.16a`）。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `template_id` | VARCHAR(40) | PK | `tpl_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户（仅本人可见） |
| `name` | VARCHAR(100) | NN | 模板名称 |
| `description` | VARCHAR(255) | ? | 模板描述 |
| `category` | VARCHAR(20) | ? | 模板分类（`会前` / `会后` / `通用`；服务层缺省填 `通用`） |
| `file_name` | VARCHAR(255) | ? | 原始文件名（按文本创建时为空） |
| `storage_key` | TEXT | ? | 本地存储相对路径（`templates/` 目录；按文本创建时为空） |
| `content_text` | TEXT | NN | 解析出的模板结构文本（注入生成提示词，≤20000 字符） |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 支持格式：DOCX / TXT / MD；大小沿用全局上传限制；也可不传文件、直接按文本创建（此时 `file_name` / `storage_key` 为空）。
- 仅本人可读/可删；删除时同步删除文件。
- 生成联动：`prepare` 与 `minutes/generate` 的 `template_id` 引用本表或内置模板 ID。

### 3.17 `async_jobs` 异步任务

长耗时 AI 任务的执行记录（ADR-3：通用任务表 + DB 队列 worker，无 Celery/Redis；`api.md 1.9`、`agent-framework.md 8`）。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `job_id` | VARCHAR(40) | PK | `job_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 归属用户（仅本人可见） |
| `job_type` | VARCHAR(40) | NN | `material_parse` / `knowledge_parse` / `audio_transcribe` / `minutes_generate` / `preparation_generate` / `agent_workflow` |
| `resource_type` | VARCHAR(40) | NN | `material` / `knowledge_document` / `audio` / `minutes` / `preparation` / `agent_run` |
| `resource_id` | VARCHAR(40) | ? , IDX | 关联资源；纪要生成受理时为空（任务结束才建资源） |
| `payload` | JSONB | ? | 任务重建参数（worker 无法跨进程传递闭包） |
| `status` | VARCHAR(20) | NN, default `pending` | 见 §五 |
| `progress` | INTEGER | NN, default `0` | 0–100 |
| `attempts` | INTEGER | NN, default `0` | 已尝试次数 |
| `max_attempts` | INTEGER | NN, default `3` | 最大尝试次数（`JOB_MAX_ATTEMPTS`） |
| `priority` | INTEGER | NN, default `0` | 预留优先级（当前按创建时间） |
| `next_run_at` | TIMESTAMPTZ | ? | 重试退避后的最早可认领时间 |
| `locked_by` | VARCHAR(100) | ? | 认领 worker 标识 |
| `locked_at` | TIMESTAMPTZ | ? | 认领时间 |
| `heartbeat_at` | TIMESTAMPTZ | ? | 心跳；长任务存活判定 |
| `error_code` | VARCHAR(40) | ? | 失败错误码（与 `api.md 1.3` 同名，如 `FILE_PARSE_FAILED` / `JOB_TIMEOUT`） |
| `error_message` | TEXT | ? | 用户可见失败文案 |
| `created_at` | TIMESTAMPTZ | NN, default now() | pending 超窗判定基准 |
| `started_at` | TIMESTAMPTZ | ? | running 超时判定基准 |
| `finished_at` | TIMESTAMPTZ | ? | 进入终态时间 |

- 索引：`(user_id, status)`、`(resource_type, resource_id)`、`user_id`、`resource_id`、`(status, next_run_at)`。
- 执行：`JOB_WORKER_ENABLED=true` 时由 `python -m app.worker` 认领；PostgreSQL 使用
  `FOR UPDATE SKIP LOCKED`，SQLite/测试退化为条件更新。
- 重试：可重试错误回到 `pending` 并按 `attempts` 指数退避；超过 `max_attempts` 落 `failed`。
- 回滚：`JOB_WORKER_ENABLED=false` 时 API 进程仍用 `BackgroundTasks` 执行（旧行为）。
- 僵尸回收：依据 `heartbeat_at` / `started_at` 与 `ASYNC_JOB_STALE_MINUTES`（默认 30 分钟）。
- 任务失败只写 `error_code`/`error_message`，资源状态由各资源自己的状态机决定（统一失败策略，见 §五）。

### 3.18 `ai_call_logs` AI 调用审计日志

AI（LLM）调用的元数据审计（`ai-design.md 3.11`；迁移 `0025_ai_call_logs` 建表、`0026_ai_call_runtime` 运行态扩展）。**只存数值与枚举标签，不存提示词、用户原文或模型输出**（日志红线）。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `log_id` | VARCHAR(40) | PK | `ail_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 归属用户 |
| `job_id` | VARCHAR(40) | ?, IDX | 关联 `async_jobs.job_id`（后台任务内产生的调用）；同步调用为空。**不建 FK**：审计 append-only，任务清理不应连坐日志 |
| `scene` | VARCHAR(40) | NN, IDX | 场景名（`ai/scenes.py` 注册表键，如 `chat`/`minutes`） |
| `purpose` | VARCHAR(20) | ? | BYOK 用途（`preparation`/`chat`/`minutes`/`extraction`；场景未映射用途时为空） |
| `model` | VARCHAR(100) | NN | 实际发出请求的模型（降级链切换后为候选模型；LLM 未调用时为配置值或 `-`） |
| `provider` | VARCHAR(200) | NN | provider 主机名（不含路径与凭证） |
| `transport` | VARCHAR(10) | NN, default `sync` | `sync` / `sse` |
| `status` | VARCHAR(10) | NN, default `success` | `running`（预创建）/ `success` / `failed` / `cancelled`，见 §五 |
| `error_code` | VARCHAR(40) | ? | 失败错误码（与 `api.md 1.3` 同名；断开 `CLIENT_DISCONNECTED`、僵尸回收 `AI_CALL_INTERRUPTED`） |
| `input_tokens` | INTEGER | ? | 累计输入 token（结构化修复重试与降级切换累计；未采集到为 NULL） |
| `output_tokens` | INTEGER | ? | 累计输出 token |
| `cost_usd` | NUMERIC(12,6) | ? | 估算成本（`ai/pricing.py` 按单价 × token；单价未知为 NULL；**非计费依据**） |
| `latency_ms` | INTEGER | NN, default `0` | 场景级耗时（含上下文收集，`ai_call_latency_ms` 指标同源） |
| `fallback_from` | VARCHAR(100) | ? | 降级链切换的起点模型（未切换为 NULL） |
| `fallback_scope` | VARCHAR(20) | ? | 降级来源标签：`none` / `global`（本期）；`user` / `scene` / `cross_provider` 为后续演进预留值 |
| `meta` | JSONB | NN, default `{}` | 纯标签扩展（如 `{"chain_len": "3"}`）；禁止提示词、用户原文与模型输出 |
| `created_at` | TIMESTAMPTZ | NN, default now() | 受理/预创建时间（= 调用开始） |
| `finished_at` | TIMESTAMPTZ | ? | 进入终态时间；`running` 行为 NULL |

- 索引：`(user_id, created_at)`、`(scene, created_at)`、`(job_id, created_at)`、`(user_id, status, created_at)`、`user_id`。
- **预创建运行态**：`services/ai_audit_service` 在调用开始 `persist_start` 落 `running` 行，收尾 `finish_call` 更新为终态并写 `finished_at`；进程崩溃残留的 `running` 行由启动回收与 `/metrics` 读取前的懒回收兜底为 `failed AI_CALL_INTERRUPTED`（窗口 `AI_AUDIT_STALE_MINUTES`，默认 30 分钟）。
- **旁路写入**：任何落库失败只记 warning 并回滚，绝不影响业务调用（`ai_audit_service` 同时写 `ai_call_*` 指标，与 DB 解耦）。
- **任务关联**：`task_runner.run_job` 经 `ai/audit.py` 绑定 job 上下文，任务体内审计行自动写 `job_id`；统计时 LEFT JOIN `async_jobs` 可得任务类型与资源。
- **流式（SSE）**：端点在返回流之前预创建，生成器 `finally` 用独立短会话收尾（成功/失败/客户端断开三条路径统一覆盖）。
- 接入点为纯 LLM 调用段（此时会话内无未提交业务写入，提交审计行不连带提交业务状态）；MVP 不对外暴露明细查询接口，聚合统计见 `api.md 1.8` 的 `ai_calls` 段。

### 3.19 `agent_sessions` Agent 会话

服务端会话（`agent-framework.md 6`；迁移 `0030_agent_framework`）。按 `user + scene + meeting` 隔离，localStorage 仅作缓存/回退。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `session_id` | VARCHAR(40) | PK | `ags_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 归属用户 |
| `meeting_id` | VARCHAR(40) | FK→meetings, ?, IDX | 关联会议（可空） |
| `scene` | VARCHAR(20) | NN | `preprocess` / `asr` / `minutes` |
| `title` | VARCHAR(200) | ? | 会话标题 |
| `status` | VARCHAR(20) | NN, default `active` | `active` / `archived` |
| `meta` | JSONB | ? | 扩展标签（如 `migrated`） |
| `created_at` / `updated_at` | TIMESTAMPTZ | NN | 通用字段 |
| `last_message_at` | TIMESTAMPTZ | ? | 最后消息时间 |

- 索引：`(user_id, scene, meeting_id, updated_at)`。

### 3.20 `agent_messages` Agent 消息

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `message_id` | VARCHAR(40) | PK | `agm_` 前缀 |
| `session_id` | VARCHAR(40) | FK→agent_sessions, NN | 所属会话（删除级联） |
| `role` | VARCHAR(20) | NN | `user` / `assistant` |
| `content` | TEXT | NN | 原文或助手回复 |
| `kind` | VARCHAR(20) | ? | `summary` / `polish` / `minutes` / `action_items` / `prepare` / `file` / `chat` |
| `structured` | JSONB | ? | 结构化候选（只作展示，不覆盖原文） |
| `sources` | JSONB | ? | 来源列表 |
| `file` | JSONB | ? | Build 模式产出文件元数据 |
| `status` | VARCHAR(20) | NN, default `completed` | `streaming` / `completed` / `failed` / `cancelled` |
| `job_id` | VARCHAR(40) | ? | 关联异步任务 |
| `meta` | JSONB | ? | 意图、运行 id、`pending_action_id` 等 |
| `created_at` | TIMESTAMPTZ | NN | 创建时间 |

- 索引：`(session_id, created_at)`。

### 3.21 `agent_runs` 工作流运行

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `run_id` | VARCHAR(40) | PK | `agr_` 前缀 |
| `session_id` | VARCHAR(40) | FK→agent_sessions, NN, IDX | 所属会话 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 归属用户 |
| `meeting_id` | VARCHAR(40) | ? | 关联会议 |
| `workflow` | VARCHAR(40) | NN | `web_fallback` / `transcribe_to_minutes` |
| `status` | VARCHAR(20) | NN, default `pending` | `pending` / `running` / `waiting` / `succeeded` / `failed` / `cancelled` |
| `current_step` | VARCHAR(60) | ? | 当前步骤名 |
| `state` | JSONB | ? | 工作流状态快照（支持从暂停点恢复） |
| `job_id` | VARCHAR(40) | ?, IDX | 关联异步任务 |
| `error_code` | VARCHAR(40) | ? | 失败错误码 |
| `error_message` | TEXT | ? | 失败文案 |
| `created_at` / `updated_at` | TIMESTAMPTZ | NN | 通用字段 |
| `started_at` / `finished_at` | TIMESTAMPTZ | ? | 起止时间 |

- 索引：`(user_id, status, created_at)`。

### 3.22 `agent_run_steps` 工作流步骤轨迹

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `step_id` | VARCHAR(40) | PK | `ags_` 前缀（步骤） |
| `run_id` | VARCHAR(40) | FK→agent_runs, NN | 所属运行 |
| `step_name` | VARCHAR(60) | NN | 步骤名 |
| `status` | VARCHAR(20) | NN | `running` / `succeeded` / `failed` / `waiting` |
| `attempt` | INTEGER | NN, default 1 | 第几次尝试 |
| `input` / `output` | JSONB | ? | 输入/输出摘要（不存完整提示词） |
| `error_code` | VARCHAR(40) | ? | 失败错误码 |
| `error_message` | TEXT | ? | 失败文案 |
| `created_at` / `finished_at` | TIMESTAMPTZ | NN / ? | 起止时间 |

- 索引：`(run_id, created_at)`。

### 3.23 `agent_pending_actions` 确认门

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `action_id` | VARCHAR(40) | PK | `aga_` 前缀 |
| `session_id` | VARCHAR(40) | FK→agent_sessions, NN | 所属会话 |
| `run_id` | VARCHAR(40) | FK→agent_runs, ? | 暂停的运行 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 归属用户 |
| `action_type` | VARCHAR(40) | NN | 当前为 `web_search` |
| `question` | TEXT | NN | 向用户展示的确认问题 |
| `payload` | JSONB | ? | 继续执行所需参数：`question`、发起时的 `options`（模型/思考开关/模板）、`audio_id` 等 |
| `status` | VARCHAR(20) | NN, default `pending` | `pending` / `approved` / `rejected` / `expired` |
| `expires_at` | TIMESTAMPTZ | ? | 过期时间 |
| `created_at` / `decided_at` | TIMESTAMPTZ | NN / ? | 创建/处理时间 |

- 索引：`(session_id, status)`；部分唯一索引 `(run_id) WHERE run_id IS NOT NULL AND status = 'pending'`
  （迁移 `0033_agent_pending_unique`，建索引前先把同一 run 的重复 pending 转 `expired`）。
- 状态置位由单条条件 UPDATE 完成（`agent_repository.claim_pending_action`），
  并发重复处理只有一个生效；重复处理与过期返回 `409 BUSINESS_RULE_VIOLATION`，拒绝不产生外部副作用。

## 四、数据关系（E-R）

- User — Meeting：一对多
- User — UserModelConfig：一对一（`user_model_configs.user_id` 主键）
- User — UserMemory：一对一（`user_memories.user_id` 主键）
- User — MeetingTemplate：一对多（仅自定义模板入库）
- User — KnowledgeDocument：一对多
- User — AICallLog：一对多（仅本人审计行，MVP 不对外暴露）
- AsyncJob — AICallLog：一对多（`ai_call_logs.job_id`，**非外键**——审计 append-only）
- KnowledgeDocument — KnowledgeChunk：一对多
- User — PersonalTask：一对多
- Meeting — MeetingMaterial：一对多
- Meeting — MeetingAudio：一对多
- Meeting — MeetingRecord：一对多
- MeetingAudio — MeetingRecord：0..1 对 0..1（`record_id`）
- Meeting — Preparation：一对多
- Meeting — MeetingMinutes：一对多
- Meeting — ActionItem：一对多
- Meeting — OpenIssue：一对多
- MeetingMaterial — DocumentChunk：一对多
- MeetingRecord — ActionItem：一对多（`source_record_id`）
- MeetingRecord — OpenIssue：一对多（`source_record_id`）
- ActionItem — PersonalTask：0..1 对 0..1（`personal_tasks.action_id` 唯一）
- User — AgentSession：一对多
- Meeting — AgentSession：一对多（可空关联）
- AgentSession — AgentMessage：一对多（删除级联）
- AgentSession — AgentRun：一对多
- AgentRun — AgentRunStep：一对多
- AgentRun — AgentPendingAction：一对多（暂停点）
- User — AgentPendingAction：一对多
- AgentRun — AsyncJob：0..1（`async_jobs.resource_id`，长任务触发的工作流）

补充要求：

- DocumentChunk 每条必须能回溯所属材料，不能只存向量丢失来源。
- 个人任务必须保留用户、来源会议与可选行动项关联。
- 纪要与准备结果用 `version`/`updated_at` 管理，避免覆盖历史。

## 五、共享状态与枚举

| 对象 | 字段 | 取值 | 说明 |
| --- | --- | --- | --- |
| Meeting | `status` | `scheduled`、`archived` | **MVP 仅两态**；预留 `in_progress`/`completed` 将来扩展 |
| Material | `processing_status` | `uploaded`、`processing`、`processed`、`failed` | 解析状态；`failed` 为活跃状态（见下） |
| Preparation | `status` | `generating`、`draft`、`confirmed`、`failed` | |
| Minutes | `status` | `draft`、`confirmed` | |
| ActionItem | `status` | `pending_confirmation`、`confirmed`、`converted`、`cancelled` | |
| PersonalTask | `status` | `todo`、`in_progress`、`completed`、`cancelled` | |
| PersonalTask | `priority` | `high`、`medium`、`low` | 任务优先级，三色标签（迁移 0032） |
| OpenIssue | `status` | `open`、`resolved`、`cancelled` | |
| AsyncJob | `status` | `pending`、`running`、`succeeded`、`failed` | 异步任务执行状态；终态不可再变（`api.md 1.9`）；可重试失败回到 `pending` |
| AICallLog | `status` | `running`、`success`、`failed`、`cancelled` | 调用审计状态；`running` 为预创建运行态，终态后不可再变 |
| AgentSession | `status` | `active`、`archived` | Agent 会话状态 |
| AgentRun | `status` | `pending`、`running`、`waiting`、`succeeded`、`failed`、`cancelled` | 工作流运行状态；`waiting` 表示等待确认门 |
| AgentRunStep | `status` | `running`、`succeeded`、`failed`、`waiting` | 步骤执行状态 |
| AgentPendingAction | `status` | `pending`、`approved`、`rejected`、`expired` | 确认门状态；`pending` 才可处理 |

流转规则：

- Meeting：`scheduled` ↔ `archived`（归档只读，MVP 不提供开始/完成操作）。
- Material：`uploaded → processing → processed | failed`；重试允许 `failed → processing`（`api.md 4.6`）。
  - **2026-11 统一失败策略（B1）**：材料/知识库解析或索引失败**落库 `failed`，保留数据库记录与已上传磁盘文件**（不回滚、不删除），同时清理半成品分块并写入 `parse_error` + `parse_error_code`；提供重试接口 `POST /materials/{id}/retry`、`POST /knowledge/documents/{id}/retry` 读取磁盘原文件重新处理。接口对失败仍返回 `201`（对象 `processing_status=failed`），不再返回 `422 FILE_PARSE_FAILED` 或执行失败清理。
- Preparation：`generating → draft → confirmed`；生成失败 `failed`；确认动作幂等（`api.md 5.6`）。异步生成（`ASYNC_JOBS_ENABLED=true`）先落 `generating` 占位行，由后台任务转 `draft`/`failed`。
- AsyncJob：`pending → running → succeeded | failed`；终态不可变。超窗 `pending`/超时 `running` 由启动回收与读取懒回收置为 `failed`（`error_code=JOB_TIMEOUT`，`api.md 1.9`）。
- AICallLog：`running → success | failed | cancelled`；`cancelled` 仅来自流式消费端提前关闭（`CLIENT_DISCONNECTED`）；进程崩溃残留的 `running` 由启动回收与 `/metrics` 懒回收置为 `failed`（`error_code=AI_CALL_INTERRUPTED`，窗口 `AI_AUDIT_STALE_MINUTES`）。
- ActionItem：`pending_confirmation → confirmed → converted`；可由待确认/已确认进入 `cancelled`；**仅 `confirmed` 可转任务**。
- PersonalTask：`todo → in_progress → completed`；未完成可 `cancelled`。
- OpenIssue：`open → resolved | cancelled`。

> 状态流转由后端校验，前端不得直接改写。

## 六、索引与约束建议

- `users(name)`：唯一索引。
- `meetings(user_id, meeting_time)`。
- `meeting_materials(meeting_id)`、`meeting_materials(user_id)`。
- `meeting_records(meeting_id, created_at)`。
- `preparations(meeting_id, created_at)`。
- `meeting_minutes(meeting_id, created_at)`。
- `action_items(meeting_id, status)`。
- `personal_tasks(user_id, status, due_date)`。
- `open_issues(meeting_id, status)`。
- `async_jobs(user_id, status)`、`async_jobs(resource_type, resource_id)`。
- `ai_call_logs(user_id, created_at)`、`ai_call_logs(scene, created_at)`、`ai_call_logs(job_id, created_at)`、`ai_call_logs(user_id, status, created_at)`。
- `document_chunks(material_id, chunk_index)`：唯一索引。
- `personal_tasks(action_id)`：唯一约束。
- `meeting_materials(client_op_id)`、`meeting_records(client_op_id)`、`action_items(client_op_id)`、`open_issues(client_op_id)`、`meeting_audio(client_op_id)`：唯一索引（可空列允许多个 NULL），迁移 `0027_client_op_id`。
- `meeting_materials(user_id, content_hash)`、`knowledge_documents(user_id, content_hash)`：增量索引复用查询（迁移 `0028_rag_content_hash`）。
- 向量索引：`document_chunks.embedding` 与 `knowledge_chunks.embedding` 已建 HNSW（`vector_cosine_ops`，迁移 `0029_rag_hnsw`）。查询期 `hnsw.ef_search` 由 `RAG_HNSW_EF_SEARCH` 控制；HNSW + 过滤会损失召回，应用层以 `RAG_ANN_OVERSAMPLE` 过采样补偿。数据量大时可在迁移外用 `CREATE INDEX CONCURRENTLY` 重建。

## 七、删除与数据一致性策略

采用**受控级联**，由业务服务在事务中显式执行，不依赖隐式数据库行为。

- **删除会议**：
  - 若存在**已转换行动项**（`action_items.status = converted`）或**引用该会议的个人任务**（`personal_tasks.meeting_id`），**禁止删除**，业务层返回 `409 BUSINESS_RULE_VIOLATION`。
  - 否则在事务中删除该会议的材料、分块、记录、准备稿、纪要、行动项与问题。
- 删除材料：删除文件对象、`document_chunks` 与向量；`meeting_records.source_material_id` 引用该材料时置空，不删除原始记录。
- 删除记录：若被行动项（`source_record_id`）或问题（`source_record_id`）引用，返回 `409 BUSINESS_RULE_VIOLATION`，避免来源失去可追溯性。
- 删除行动项：已转换为任务的不允许直接删除（应取消状态或保留关联），避免任务失去来源。
- 用户删除：MVP 不提供。
- 文件存储不支持事务时，须设计失败补偿/清理机制。

## 八、数据库与迁移协作规范

1. A 负责主数据库结构和 Alembic 迁移合并。
2. B 在开发 RAG、纪要、行动项之前，先向 A 提交实体字段和关系需求。
3. C 通过 API 响应模型获取数据，不直接依赖数据库内部实现。
4. 每个涉及数据库结构的 PR，必须包含迁移文件或明确说明无需迁移。
5. 不允许多人同时基于同一个旧迁移创建冲突的 Alembic heads。
6. 删除会议、资料、纪要等关联数据时，应通过业务服务统一处理关联清理与文件删除。
7. 已应用（记录进 `alembic_version`）的迁移文件不可再修改，必须新增后续迁移。

## 九、基础设施：PostgreSQL 与 pgvector

| 项目 | 取值 | 说明 |
| --- | --- | --- |
| 镜像 | `pgvector/pgvector:pg16` | 已内置 pgvector 扩展二进制 |
| 持久化 | 具名卷 `pgdata` → `/var/lib/postgresql/data` | 容器重建不丢数据 |
| 容器内地址 | `db:5432` | 容器之间走 Docker 内部网络与服务名解析 |
| 宿主机直连 | `localhost:5432` | 仅用于宿主机直接运行后端，不用于容器间通信 |

pgvector 扩展**由 Alembic 统一管理**：迁移 `0002_enable_pgvector` 执行 `CREATE EXTENSION IF NOT EXISTS vector`。镜像只提供扩展二进制，扩展必须在目标库内启用后 `vector` 类型才可用，因此该迁移不可省略。

- 该迁移幂等，重复执行安全。
- `downgrade` 不做级联删除：若已有表/列依赖 `vector` 类型，降级会明确失败，而不是静默摧毁这些对象。
- 禁止使用 `docker-entrypoint-initdb.d` 之类的 initdb SQL 来启用扩展——initdb 脚本只在数据目录为空的首次启动时执行，不受版本控制，无法随代码演进。

验证方式见 `docs/development.md` 的「数据库启动验证」章节（`scripts/verify-db.ps1` / `scripts/verify-db.sh`）。
