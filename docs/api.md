# API 契约

本文件是前端、后端与 AI 模块的共同接口基线，也是接口的唯一事实来源。运行期以 FastAPI 自动生成的 OpenAPI 文档为准；设计与实现冲突时先更新本文件。

> 状态：MVP 全部实现。`[扩展]` 表示非 MVP、先定义结构但不实现。

## 一、统一约定

| 项目 | 约定 |
| --- | --- |
| API 前缀 | `/api/v1` |
| 数据格式 | JSON；文件上传 `multipart/form-data` |
| 身份认证 | `Authorization: Bearer <access_token>` |
| 登录标识 | 唯一 `name` + `password`（无 email） |
| 主键 | 后端生成，带前缀字符串（见 `database.md` 二） |
| 时间格式 | ISO 8601，带时区（如 `2026-10-01T09:30:00+08:00`）；仅日期用 `YYYY-MM-DD` |
| ID 生成 | 前端不生成业务主键 |
| 成功响应 | 统一包裹为 `{ "status": "success", "data": ... }` |
| 错误响应 | 统一为 `{ "status": "error", "error_code", "message", "retryable" }` |

### 1.1 成功响应

```json
{ "status": "success", "data": {} }
```

列表统一放在 `data.items`，分页信息放在 `data.pagination`。

### 1.2 错误响应

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数不合法",
  "retryable": false,
  "details": { "field": "title", "reason": "required" }
}
```

- `retryable` 为布尔值；临时故障为 `true`，权限/参数/业务规则错误为 `false`。
- `details`（可选）：结构化错误信息，用于字段校验错误与 `FILE_PARSE_FAILED.reason`；不得包含堆栈、密钥、SQL 或提示词。
- 前端按 `error_code` 分支，不依赖 `message` 文案。

### 1.3 错误码总表

| 错误码 | 典型 HTTP | 含义 | 可重试 |
| --- | ---: | --- | --- |
| `AUTH_REQUIRED` | 401 | 未登录或凭证失效 | 否 |
| `PERMISSION_DENIED` | 403 | 已登录但无权操作（本 MVP 一般用 404 代替） | 否 |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在或不可访问 | 否 |
| `VALIDATION_ERROR` | 422 | 字段缺失、格式错误或值不合法 | 否 |
| `FILE_TYPE_NOT_SUPPORTED` | 415 | 文件类型不支持 | 否 |
| `FILE_TOO_LARGE` | 413 | 文件超过大小限制 | 否 |
| `FILE_PARSE_FAILED` | 422 | 文件无法解析（原因见 `details.reason`，见下；模板上传同步返回。材料/知识库解析失败改为落库 `failed` + `parse_error_code`，见 §4.2/§2.6，不返回 422） | 通常否 |
| `MODEL_TIMEOUT` | 504 | 模型调用超时 | 是 |
| `MODEL_OUTPUT_INVALID` | 502 | 模型输出无法解析或未通过校验（经 1 次修复重试后仍失败时 `retryable=true`） | 视情况 |
| `MODEL_CONFIG_INVALID` | 400 | 模型配置校验失败（密钥无效/额度不足等） | 否 |
| `MODEL_CONFIG_REQUIRED` | 400 | 用户未配置模型 Key（BYOK） | 否 |
| `MODEL_QUOTA_EXCEEDED` | 402 | 模型额度不足 | 否 |
| `RATE_LIMITED` | 429 | 请求频率超过限制（`details.scope="concurrency"` 时表示模型调用并发排队超时） | 是 |
| `MODEL_UPSTREAM_UNAVAILABLE` | 503 | 模型服务熔断打开（近期失败过多，`details.circuit="open"`），冷却后自动恢复 | 是 |
| `MODEL_INPUT_TOO_LONG` | 413 | 输入超出模型上下文上限（发送前预检或服务商返回，`details.estimated_tokens/limit` 或 `details.reason="context_length"`） | 否 |
| `JOB_TIMEOUT` | — | 异步任务超时（作为任务的 `error_code` 返回，见 §1.9；不直接作为 HTTP 错误体） | 是 |
| `BUSINESS_RULE_VIOLATION` | 409 | 当前状态不允许该操作 | 否 |
| `INTERNAL_ERROR` | 500 | 未预期的服务端错误 | 视情况 |

> `400` 仅用于无法解析的请求体（malformed body），返回 `VALIDATION_ERROR`。

`FILE_PARSE_FAILED` 的稳定原因（对齐解析层，写入 `details.reason`）：

| reason | 含义 |
| --- | --- |
| `empty_content` | 文件内容为空 |
| `unsupported_format` | 扩展名不受支持（仅 pdf/docx/txt） |
| `no_text_layer` | PDF 无文本层（扫描件，暂不支持 OCR） |
| `encrypted_pdf` | PDF 已加密 |
| `invalid_file` | 文件读取/格式损坏 |
| `parse_failed` | 其他解析异常 |

### 1.4 分页与筛选

- `page`：从 `1` 开始，默认 `1`。
- `page_size`：默认 `20`，最大 `100`。
- `sort_by`、`sort_order`（`asc`/`desc`）：仅接口明确支持时使用。

分页响应：

```json
{
  "status": "success",
  "data": {
    "items": [],
    "pagination": { "page": 1, "page_size": 20, "total": 0, "total_pages": 0 }
  }
}
```

### 1.5 PATCH 更新语义

- 请求体未出现的字段：保持原值。
- 字段传 `null`：仅当该字段允许为空时清空，否则返回 `422 VALIDATION_ERROR`。
- 不允许客户端更新 `id`、`user_id`、`created_at` 等服务端管理字段。
- 更新成功返回更新后的完整资源对象。

### 1.6 权限与归属

- 所有业务数据按当前登录用户过滤；请求体中的 `user_id` 不作为权限依据。
- 越权访问（含资源不存在）统一返回 `404 RESOURCE_NOT_FOUND`。
- 下级资源（材料、记录、准备、纪要、行动项、问题）通过所属会议校验归属。

### 1.7 时间

- 库内统一 `TIMESTAMPTZ`，以 **UTC** 存储；接口返回带时区 ISO 8601（如 `2026-10-01T09:30:00+08:00`）；仅日期字段用 `YYYY-MM-DD`。

### 1.8 健康检查与运维探针（豁免信封）

以下探针端点不套用 `{ "status": "success", "data": ... }` 信封，直接返回探针结果：

| 方法 | 路径 | 成功响应 |
| --- | --- | --- |
| GET | `/health` | `{ "status": "ok" }` |
| GET | `/api/v1/health/db` | `{ "status": "ok", "database": "up" }`（数据库不可用返回 503 统一错误体） |
| GET | `/api/v1/metrics` | RAG 可观测性指标快照（**需登录**；`METRICS_ENABLED=false` 时返回 404，见下） |

`GET /api/v1/metrics`（运维端点，**需登录**（任意已登录用户）；`METRICS_ENABLED=false` 时返回 404 隐藏；进程内累计，重启清零）：

```json
{
  "generated_at": 1767000000.0,
  "counters": { "rag_judge_total/true": 9, "rag_judge_total/false": 2, "rag_judge_total/fallback": 1 },
  "rag_judge": { "triggered": 12, "true": 9, "false": 2, "fallback": 1,
                  "ratios": { "true": 0.75, "false": 0.1667, "fallback": 0.0833 } },
  "windows": {
    "retrieval_total_ms": { "samples": 30, "p50": 120.5, "p95": 890.1, "max": 1200.0,
                             "mean": 150.2, "median": 120.5, "insufficient": false }
  },
  "alerts": { "last_fired_monotonic": {} }
}
```

- `rag_judge.triggered` = Judge 实际调用 LLM 的次数（true+false+fallback）；高分带直通与 Judge 禁用不计入；
- `windows.*` 来自滑动窗口（约最近 1000 次），样本 < 20 时 `p50/p95` 为 `null` 且 `insufficient=true`；
- 计数器还包含流式问答埋点：`chat_stream_total`（进入 SSE 流的次数）、`chat_stream_error_total`（首增量前 JSON 错误与流内 `error` 事件合计）；窗口 `chat_stream_first_token_ms` 为流式首 token 延迟（见 5.7a）；
- 计数器还包含模型调用底座埋点（见 `ai-design.md 3.6`）：`ai_retry_total`（实际发出的重试次数）、`ai_concurrency_rejected_total`（模型并发排队超时拒绝）、`ai_circuit_open_total`（熔断打开拦截次数）、`ai_fallback_total`（降级链切换模型次数，见 3.9）；
- 不含任何查询原文、提示词或用户内容（与日志红线一致）。

### 1.9 异步任务（Job，202 受理）

长耗时 AI 任务（材料/知识库解析、音频转写、纪要生成、会前准备）在 `ASYNC_JOBS_ENABLED=true`（默认）时异步执行：受理端点返回 `202`，`data` 为**受理载荷**而非业务对象，前端轮询下表任务端点获取进度与终态。开关关闭时回退原同步契约（200/201 + 业务对象），用于回滚。

任务对象（`JobRead`）：

```json
{
  "job_id": "job_xxx",
  "job_type": "material_parse",
  "status": "running",
  "resource_type": "material",
  "resource_id": "mat_xxx",
  "progress": 60,
  "error_code": null,
  "error_message": null,
  "created_at": "2026-11-10T09:00:00+08:00",
  "started_at": "2026-11-10T09:00:01+08:00",
  "finished_at": null
}
```

202 受理载荷（`JobAccepted`）：`{ "job": { …任务对象… } }`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/jobs/{job_id}` | 任务详情（仅本人；超时的 `pending`/`running` 读取时懒回收为 `failed`） |
| GET | `/api/v1/jobs` | 本人任务分页列表，可选查询参数 `resource_type` / `resource_id` 过滤 |

规则：

- `status` 状态机：`pending → running → succeeded | failed`，终态不可再变。
- `job_type`：`material_parse` / `knowledge_parse` / `audio_transcribe` / `minutes_generate` / `preparation_generate`。
- `resource_id`：关联资源 id；**纪要生成在任务结束才创建纪要**，受理时为 `null`；**会前准备**为 `generating` 占位稿 id（任务结束转 `draft`/`failed`，见 5.2）。
- `progress`：0–100（10/60/90 等进度点，`succeeded` 时置 100）。
- `error_code` 失败错误码与 §1.3 同名（`FILE_PARSE_FAILED` / `MODEL_CONFIG_REQUIRED` / `MODEL_TIMEOUT` / `JOB_TIMEOUT` / `INTERNAL_ERROR` …），`error_message` 为可展示文案；任务失败**不改变统一失败策略**——资源仍落 `failed` 并保留记录与文件（`ai-design.md 6.4`）。
- 超时回收：单实例 + `BackgroundTasks`，进程重启丢失 `pending` 任务；启动与读取时按 `ASYNC_JOB_STALE_MINUTES`（默认 30 分钟）把超窗 `pending`（以 `created_at`）与超时 `running`（以 `started_at`）回收为 `failed` + `JOB_TIMEOUT`。
- 归属隔离：任务仅本人可见，越权/不存在均返回 `404 RESOURCE_NOT_FOUND`。

## 二、用户认证（M01，A）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/logout` | 退出 |
| GET | `/api/v1/auth/me` | 当前用户 |

> 鉴权：登录/注册成功后返回 `access_token`（**HS256 JWT**，有效期 `ACCESS_TOKEN_EXPIRE_MINUTES`），后续请求携带 `Authorization: Bearer <access_token>`。MVP **不提供 refresh token**；退出为无状态——服务端返回成功，客户端清除本地令牌。

用户对象：

```json
{ "user_id": "usr_xxx", "name": "张三", "created_at": "2026-10-01T09:00:00+08:00" }
```

### 2.1 注册 `POST /api/v1/auth/register`

请求：

```json
{ "name": "张三", "password": "user-password" }
```

响应 `201`：

```json
{
  "status": "success",
  "data": {
    "user": { "user_id": "usr_xxx", "name": "张三", "created_at": "2026-10-01T09:00:00+08:00" },
    "access_token": "...",
    "token_type": "bearer"
  }
}
```

规则：`name` 唯一；密码不落明文、不返回哈希；重复 `name` 返回 `422 VALIDATION_ERROR`（或 `409 BUSINESS_RULE_VIOLATION`）。

### 2.2 登录 `POST /api/v1/auth/login`

请求：

```json
{ "name": "张三", "password": "user-password" }
```

响应 `200`：结构同注册响应。凭证无效返回 `401 AUTH_REQUIRED`。

### 2.3 退出 `POST /api/v1/auth/logout`

无请求体。响应 `200`：

```json
{ "status": "success", "data": { "logged_out": true } }
```

### 2.4 当前用户 `GET /api/v1/auth/me`

响应 `200`：`data` 为用户对象。

### 2.5 模型配置（LLM 用户自带 BYOK，M04，B）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/me/settings/model` | 读取当前生效的模型配置（密钥脱敏） |
| PUT | `/api/v1/me/settings/model` | 保存/替换 LLM 自备配置（probe 校验后加密存库） |
| GET | `/api/v1/me/settings/model/provider-models` | 拉取当前服务商可用模型清单（会话内模型选择器用） |
| PUT | `/api/v1/me/settings/model/purposes` | 保存按用途覆盖的模型名 |
| DELETE | `/api/v1/me/settings/model` | 清空自备配置，回退服务端全局 |

向量模型（Embedding）不支持用户自备，始终使用服务端 `docker/.env` 的 `EMBEDDING_*` 全局配置；本接口仅接受 LLM 三字段。

PUT 请求（LLM 字段可整体省略，省略即清空 LLM 自备配置）：

```json
{
  "llm_api_base": "https://api.example.com/v1",
  "llm_api_key": "sk-...",
  "llm_model": "model-name"
}
```

按用途模型请求（`PUT /api/v1/me/settings/model/purposes`，整体替换用途覆盖；空对象 `models: {}` 清除全部覆盖）：

```json
{
  "models": {
    "preparation": "prep-model",
    "chat": "chat-model",
    "minutes": "minutes-model",
    "extraction": "extract-model"
  }
}
```

- 用途：`preparation`（会前准备）、`chat`（会议问答与整理）、`minutes`（纪要生成）、`extraction`（行动项/问题提取）。
- 仅覆盖模型名，API 地址与密钥沿用大模型配置；未覆盖的用途使用 `llm_model`。
- 设置用途模型前必须已有生效的大模型配置。
- 保存基础模型配置不会清除用途覆盖；使用 `models: {}` 清除全部用途覆盖。

GET/PUT 响应（密钥一律脱敏，不回显明文）：

```json
{
  "status": "success",
  "data": {
    "llm_api_base": "https://api.example.com/v1",
    "llm_model": "model-name",
    "llm_api_key_masked": "sk-...abcd",
    "llm_source": "user",
    "llm_purpose_models": {
      "minutes": "minutes-model"
    },
    "embedding_api_base": "https://api.example.com/v1",
    "embedding_model": "text-embedding-1024",
    "embedding_api_key_masked": "",
    "embedding_source": "global",
    "embedding_dim": 1024,
    "llm_probe_verified": true
  }
}
```

规则：
- 密钥 `Fernet` 加密存库，永不明文返回；`_masked` 仅展示前后缀。
- `_masked` 仅在来源为 `user` 时返回值；`global` / `none` 返回空字符串，避免向普通用户泄露服务端全局密钥片段。
- 保存时 probe 实测：真实调用一次 LLM（单次、不重试、15s 超时），HTTP 200 且返回 `choices` 即通过，不要求正文非空（兼容思考型模型）。密钥无效返回 `400 MODEL_CONFIG_INVALID`；超时、服务端 5xx 和额度不足保留原错误码（`MODEL_TIMEOUT` / `INTERNAL_ERROR` / `MODEL_QUOTA_EXCEEDED`）及 `retryable` 语义。
- probe 遇到 `429 RATE_LIMITED` 时视为密钥认证已通过，**放行保存**，响应带 `llm_probe_verified: false` 提示“未完成调用验证”；其余情况该字段为 `true`（GET 响应恒为 `true`）。
- 保存前校验 `api_base`：默认只允许 HTTPS 公网地址，拒绝本机/私有/保留地址、URL 内嵌凭证和 query/fragment；自建本地模型需显式开启 `ALLOW_PRIVATE_MODEL_ENDPOINTS=true`。
- 向量模型（Embedding）为服务端统一配置：`embedding_source` 只会是 `global`（`docker/.env` 已配置）或 `none`（未配置）；未配置时 RAG/知识库/材料索引返回 `400 MODEL_CONFIG_REQUIRED`，用户侧无法自行修复，需管理员填写 `EMBEDDING_*`。
- 默认 `ALLOW_GLOBAL_FALLBACK=false`：未配置 BYOK LLM 的用户不会自动使用服务端全局 Key；AI 接口返回 `400 MODEL_CONFIG_REQUIRED`。
- 仅当 `ALLOW_GLOBAL_FALLBACK=true` 时 LLM 按“用户配置 > 服务端全局（`docker/.env`）”回退；该开关不影响 Embedding（始终为服务端配置）。
- `llm_source` / `embedding_source` 表示该提供方生效来源：`user`（仅 LLM，用户自备）、`global`（服务端全局）、`none`（未配置）；两者独立判定。
- `llm_purpose_models` 返回已保存的用途模型覆盖；未知用途或空模型名在写入时返回 `422`，未配置大模型时写入返回 `400 MODEL_CONFIG_INVALID`。
- 轮换 `SECRET_KEY` 时设置 `SECRET_KEY_PREVIOUS` 为旧值以解密既有密文；新写入使用当前 `SECRET_KEY`。确认全部配置已重新保存后可移除旧值。
- 无法解密既有密文时返回 `400 MODEL_CONFIG_INVALID`；可调用 `DELETE /me/settings/model` 清除后重新配置。
- 模型额度不足返回 `402 MODEL_QUOTA_EXCEEDED`；密钥无效/配置错误返回 `400 MODEL_CONFIG_INVALID`。

`GET /me/settings/model/provider-models`：用当前生效的 LLM 配置真实调用服务商 `GET /models`（OpenAI 兼容），返回 `data.llm_model`（已保存默认模型）与 `data.models`（排序后的模型 id 清单）。未配置 LLM 返回 `400 MODEL_CONFIG_REQUIRED`；服务商失败沿用统一错误体（超时/网络/密钥无效等），前端据此回退为仅展示项目预设清单。

### 2.6 个人知识库

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/knowledge/documents` | 上传 PDF / DOCX / TXT，解析、分块并建立向量索引 |
| GET | `/api/v1/knowledge/documents` | 当前用户知识库文档分页列表 |
| GET | `/api/v1/knowledge/documents/{document_id}` | 文档详情 |
| POST | `/api/v1/knowledge/documents/{document_id}/retry` | 重新解析/索引处理失败的文档（仅 `failed`） |
| DELETE | `/api/v1/knowledge/documents/{document_id}` | 删除文档、分块和向量索引 |
| POST | `/api/v1/knowledge/search` | 按语义检索当前用户知识库 |

上传使用 `multipart/form-data`，字段 `file`。文档对象：

```json
{
  "document_id": "kdoc_xxx",
  "file_name": "项目手册.pdf",
  "type": "pdf",
  "processing_status": "processed",
  "parse_error": null,
  "parse_error_code": null,
  "created_at": "2026-10-01T09:00:00+08:00"
}
```

`processing_status`：`uploaded` / `processing` / `processed` / `failed`。`parse_error_code`：失败错误码（如 `FILE_PARSE_FAILED` / `MODEL_CONFIG_REQUIRED` / `INTERNAL_ERROR`），供前端映射文案。

检索请求：

```json
{ "query": "上线检查项", "top_k": 5, "min_score": 0.3 }
```

检索响应：

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "document_id": "kdoc_xxx",
        "file_name": "项目手册.pdf",
        "excerpt": "上线前需完成……",
        "score": 0.82
      }
    ]
  }
}
```

规则：
- 所有文档、分块和检索结果严格限定当前用户。
- 文件大小上限沿用 `MAX_UPLOAD_MB`；仅支持 PDF / DOCX / TXT。
- 解析失败返回 `201`，对象 `processing_status=failed` 并带 `parse_error` / `parse_error_code`，**记录与磁盘文件保留**（统一失败策略，见 `database.md 五`）；不支持的类型返回 `415 FILE_TYPE_NOT_SUPPORTED`。
- 重试 `POST /knowledge/documents/{document_id}/retry`：仅 `failed` 可重试，读取磁盘原文件重新解析/索引，成功转 `processed` 并清空错误；`processing` 或非 `failed` 返回 `409`（`details.reason=document_processing` / `document_not_failed`）；原文件丢失返回 `404`。
- **异步模式（`ASYNC_JOBS_ENABLED=true`，默认）**：上传与重试均返回 `202` + `data = { "job": … }`（`job_type=knowledge_parse`，见 `api.md 1.9`），文档对象经详情接口查询（受理时为 `uploaded`）；开关关闭时按上述同步 `201`/`200` 返回。
- 删除文档同步删除分块与向量索引，删除后不得再被检索。
- 知识库检索默认不混入会议问答；问答中选择 `context_scope=knowledge_base` 时仅检索知识库。

### 2.7 记忆中心

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/me/memory` | 读取当前用户的记忆/画像 |
| PUT | `/api/v1/me/memory` | 保存或替换记忆 |
| DELETE | `/api/v1/me/memory` | 清除记忆 |

请求：

```json
{
  "role": "产品经理",
  "work_scenarios": "B2B SaaS 产品规划",
  "communication_style": "结论先行、简洁",
  "preferred_minutes_template": "concise"
}
```

响应：

```json
{
  "status": "success",
  "data": {
    "role": "产品经理",
    "work_scenarios": "B2B SaaS 产品规划",
    "communication_style": "结论先行、简洁",
    "preferred_minutes_template": "concise",
    "updated_at": "2026-10-01T09:00:00+08:00"
  }
}
```

规则：
- 记忆由用户显式维护；当前不自动从会议内容提取偏好。
- `preferred_minutes_template` 可空；取值可以是内置枚举值（`standard`/`concise`/`task_list`）或模板清单中的模板 id（5.16a）；生成纪要未显式传 `template`/`template_id` 时使用该偏好，否则回退 `standard`。
- 记忆只用于调整准备重点、纪要表达和问答表达；不得覆盖材料事实、来源、权限或业务规则。
- 按用途筛选：会前准备使用角色/场景/表达偏好；纪要使用表达偏好与模板偏好；问答使用表达偏好；行动项/问题提取不使用记忆。
- 所有读取和写入严格限定当前用户。

### 2.8 音频转写

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/audio` | 上传 MP3 / WAV / M4A / WEBM，转写为文本 |
| GET | `/api/v1/meetings/{meeting_id}/audio` | 音频列表 |
| GET | `/api/v1/audio/{audio_id}` | 音频详情 |
| PATCH | `/api/v1/audio/{audio_id}` | 修改转写文本 |
| POST | `/api/v1/audio/{audio_id}/retry` | 重新转写 |
| POST | `/api/v1/audio/{audio_id}/confirm` | 确认转写并创建会议记录 |
| DELETE | `/api/v1/audio/{audio_id}` | 删除未确认音频 |
| POST | `/api/v1/meetings/{meeting_id}/audio/live/start` | 开始实时录音会话（创建 `processing` 音频） |
| POST | `/api/v1/audio/{audio_id}/live/chunk` | 上传实时录音分片并转写追加 |
| POST | `/api/v1/audio/{audio_id}/live/finish` | 结束实时会话：合并分片、落定状态（幂等） |
| POST | `/api/v1/audio/{audio_id}/segments/{seq}/retry` | 重试某个转写失败的分片（仅实时会话中） |
| PATCH | `/api/v1/audio/{audio_id}/segments/marker` | 设置/清除分段标记（重点/决议/疑问） |

音频对象：

```json
{
  "audio_id": "aud_xxx",
  "meeting_id": "mtg_xxx",
  "file_name": "meeting.mp3",
  "type": "mp3",
  "status": "transcribed",
  "transcript": "转写文本……",
  "segments": [
    { "seq": 1, "offset_seconds": 0, "text": "第一段……", "marker_type": null, "error": null }
  ],
  "error": null,
  "record_id": null,
  "created_at": "2026-10-01T09:00:00+08:00",
  "updated_at": "2026-10-01T09:00:00+08:00"
}
```

`status`：`uploaded` / `processing` / `transcribed` / `failed` / `confirmed`。

规则：
- 上传使用 `multipart/form-data`，字段 `file`；大小上限沿用 `MAX_UPLOAD_MB`。
- **异步模式（`ASYNC_JOBS_ENABLED=true`，默认）**：上传（`POST /meetings/{meeting_id}/audio`）与重试（`POST /audio/{audio_id}/retry`）返回 `202` + `data = { "job": … }`（`job_type=audio_transcribe`，见 `api.md 1.9`）；音频对象经详情接口查询（受理时为 `uploaded`）。开关关闭时同步转写并按 `201`/`200` 返回业务对象。
- 转写同步调用 OpenAI 兼容的 `/audio/transcriptions`，服务端配置 `ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL`；未配置返回 `400 MODEL_CONFIG_REQUIRED`。
- 转写成功后用户可修订文本；只有 `transcribed` 且文本非空才能确认。
- 确认创建一条 `record_type=transcript` 的会议记录，确认幂等；已确认音频不能重新转写或删除。
- 失败可重试；失败原因返回 `error`，不覆盖已有成功文本。
- 所有音频、转写和记录严格限定当前用户。

实时录音（分片边录边转）规则：
- `live/start` 请求体 `{ "file_type": "webm" }`，创建 `processing` 状态音频并返回；录音内每段分片通过 `live/chunk` 追加。
- `live/chunk` 使用 `multipart/form-data`：`file`（完整可解码分片）+ `seq`（从 1 连续递增）+ `offset_seconds`（录音内相对秒数）；`seq` 不连续返回 `422 VALIDATION_ERROR`。
- 分片逐片转写：单片失败只在该分段写入 `error`，不中断会话；`transcript` 始终为各分段成功文本按 `\n` 拼接。
- `live/finish` 将分片按 `seq` 合并为单一音频文件（`storage_key` 指向合并文件），删除分片文件；有文本置 `transcribed`，否则 `failed`；重复调用幂等。
- 实时会话中可通过 `segments/{seq}/retry` 对失败分片重试（依赖分片文件仍在）；会话结束后分片已删除，仅可整体重新转写或修订文本。
- `PATCH segments/marker` 请求体 `{ "seq": 1, "marker_type": "highlight" | "decision" | "question" | null }`；未知分段返回 `404`。
- 修订全文（`PATCH /audio/{id}`）后按行重拆 `segments`，沿用原分段的相对时间与标记。

## 三、会议管理（M02，A）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings` | 会议列表 |
| POST | `/api/v1/meetings` | 创建会议 |
| GET | `/api/v1/meetings/{meeting_id}` | 会议详情 |
| PATCH | `/api/v1/meetings/{meeting_id}` | 编辑会议 |
| DELETE | `/api/v1/meetings/{meeting_id}` | 删除会议及关联数据 |
| POST | `/api/v1/meetings/{meeting_id}/archive` | 归档会议 |

会议对象：

```json
{
  "meeting_id": "mtg_xxx",
  "title": "项目周会",
  "topic": "进度与风险",
  "meeting_time": "2026-10-02T14:00:00+08:00",
  "status": "scheduled",
  "created_at": "2026-10-01T09:00:00+08:00",
  "updated_at": "2026-10-01T09:00:00+08:00",
  "archived_at": null
}
```

- `status` MVP 取值：`scheduled`、`archived`（见 `database.md` 五）。

### 3.1 列表

查询参数：`page`、`page_size`、`status`（MVP）；`keyword`、`start_time`、`end_time` 为后续增强。

响应 `200`：分页结构，`items` 为会议对象数组，按 `meeting_time`/`created_at` 倒序。

### 3.2 创建

```json
{ "title": "项目周会", "topic": "进度与风险", "meeting_time": "2026-10-02T14:00:00+08:00" }
```

`title` 必填；`topic`、`meeting_time` 可为空。响应 `201`，`data` 为会议对象。

### 3.3 详情 `GET /api/v1/meetings/{meeting_id}`

响应 `200`：`data` 为会议基础信息（关联资源由各子接口分别获取）。

### 3.4 编辑 `PATCH /api/v1/meetings/{meeting_id}`

可更新字段：`title`、`topic`、`meeting_time`。响应 `200` 为更新后对象。

### 3.5 删除 `DELETE /api/v1/meetings/{meeting_id}`

响应 `200`：

```json
{ "status": "success", "data": { "deleted": true, "meeting_id": "mtg_xxx" } }
```

- 若该会议存在**已转换的行动项**或**引用它的个人任务**，返回 `409 BUSINESS_RULE_VIOLATION`，禁止删除。
- 其余关联数据处理遵循 `database.md 七`。

### 3.6 归档 `POST /api/v1/meetings/{meeting_id}/archive`

响应 `200`：返回 `status = archived` 的会议对象。归档后只读（不允许编辑或触发 AI 生成）。

## 四、会议资料与记录（M03、M06）

### 4.1 材料对象

```json
{
  "material_id": "mat_xxx",
  "meeting_id": "mtg_xxx",
  "file_name": "项目方案.pdf",
  "type": "pdf",
  "source": "会前材料",
  "processing_status": "processed",
  "parse_error": null,
  "parse_error_code": null,
  "created_at": "2026-10-01T09:10:00+08:00"
}
```

- `processing_status`：`uploaded` / `processing` / `processed` / `failed`。`failed` 为活跃状态：解析/索引失败落库 `failed` 并保留记录与文件，可经 §4.6 重试（统一失败策略，见 `database.md 五`）。
- `parse_error_code`：失败错误码（如 `FILE_PARSE_FAILED` / `MODEL_CONFIG_REQUIRED` / `INTERNAL_ERROR`），供前端映射文案。
- 允许 `pdf` / `docx` / `txt`；单文件 ≤ `MAX_UPLOAD_MB`（默认 20MB）。
- 不暴露 `storage_key`、文件系统路径与未脱敏异常。

### 4.2 上传材料 `POST /api/v1/meetings/{meeting_id}/materials`

请求类型：`multipart/form-data`。字段：`file`（必填，单个）、`source`（可选，来源标识，前端已知取值：手动上传、`本地工作区`（会议详情/管理页手动导入）、`本地文件夹自动导入`（新建会议选文件夹后自动导入）、`AI 生成`（Build 模式文件三处保存之会议资料副本））、`material_type`（可选，缺省由后端按扩展名推断；对应响应与数据库的 `type`）。

响应 `201`：材料对象。当前为同步解析/索引，成功时 `processing_status = processed`，文件类型不支持 `415`，过大 `413`。

> 同名文件不去重（后端无唯一约束）：同名跳过由前端在自动/手动导入前以 `file_name` 集合判定；`POST` 侧不做内容比对或覆盖。

> **解析/索引失败（2026-11 统一失败策略）**：接口仍返回 `201`，材料对象 `processing_status=failed` 并带 `parse_error`（可展示原因）与 `parse_error_code`（如 `FILE_PARSE_FAILED`）。**记录、分块清理与已落盘文件全部保留**（不回滚、不删除），材料列表可见该条目；前端展示失败原因并可调用 §4.6 重试。未预期的服务端异常同样落 `failed`（`parse_error_code=INTERNAL_ERROR`），不再返回 `500`。

> **异步模式（`ASYNC_JOBS_ENABLED=true`，默认）**：解析/索引交后台任务，响应改为 `202` + `data = { "job": … }`（`api.md 1.9`）；材料对象经 `GET /api/v1/materials/{material_id}` 查询，受理时通常为 `uploaded`。开关关闭时保持上述同步 `201` 契约。

### 4.3 材料列表 `GET /api/v1/meetings/{meeting_id}/materials`

查询参数：`page`、`page_size`。响应 `200`：分页结构，`items` 为材料对象数组，按 `created_at` 倒序。

### 4.4 材料详情 `GET /api/v1/materials/{material_id}`

响应 `200`：材料对象（含 `parse_error` 与 `parse_error_code`，失败时用于前端提示）。

### 4.5 删除材料 `DELETE /api/v1/materials/{material_id}`

响应 `200`：`{ "status": "success", "data": { "deleted": true, "material_id": "mat_xxx" } }`。
删除后相关分块与向量索引同步清理，RAG 不得再检索到；引用该材料的 `meeting_records.source_material_id` 置空。

### 4.6 重试材料处理 `POST /api/v1/materials/{material_id}/retry`

对 `processing_status=failed` 的材料读取磁盘原文件重新解析/索引。响应 `200` 为处理后的材料对象（成功转 `processed` 并清空 `parse_error`/`parse_error_code`；再次失败保持 `failed` 并刷新错误信息，接口不抛错）。

- 仅 `failed` 可重试：`processing` 返回 `409`（`details.reason=material_processing`），其余状态返回 `409`（`details.reason=material_not_failed`）。
- 原文件已丢失返回 `404 RESOURCE_NOT_FOUND`（提示重新上传）；归档会议不可重试（沿用可变会议校验）。
- **异步模式**：返回 `202` + `data = { "job": … }`（`job_type=material_parse`），处理结果经任务与材料详情查询；开关关闭时按上述 `200` 同步返回。

### 4.7 音频转写 `POST /api/v1/materials/{material_id}/transcribe` [扩展]

非 MVP。一旦实现必须固定同步或 `202` 契约并写入 OpenAPI。

### 4.8 记录对象

```json
{
  "record_id": "rec_xxx",
  "meeting_id": "mtg_xxx",
  "content": "讨论记录正文",
  "record_type": "manual",
  "marker_type": null,
  "source_material_id": null,
  "created_at": "2026-10-01T09:15:00+08:00",
  "updated_at": "2026-10-01T09:15:00+08:00"
}
```

`record_type`：`manual` / `transcript` / `imported`。
`marker_type`：`highlight` / `decision` / `question`，或 `null`；每条记录最多一个标记。

### 4.9 新增记录 `POST /api/v1/meetings/{meeting_id}/records`

```json
{ "content": "讨论记录正文", "record_type": "manual", "marker_type": "decision" }
```

`content` 必填；`marker_type` 可选。响应 `201` 为记录对象。

### 4.10 记录列表 `GET /api/v1/meetings/{meeting_id}/records`

查询参数：`page`、`page_size`。响应 `200`：分页结构。

### 4.11 编辑记录 `PATCH /api/v1/records/{record_id}`

可更新字段：`content`、`marker_type`。传 `marker_type: null` 清除标记；归档会议不可修改。响应 `200` 为更新后记录对象。

### 4.12 删除记录 `DELETE /api/v1/records/{record_id}`

响应 `200`：`{ "status": "success", "data": { "deleted": true, "record_id": "rec_xxx" } }`。
若该记录被行动项或问题引用，返回 `409 BUSINESS_RULE_VIOLATION`，以保留来源可追溯性。

## 五、AI 应用（M04、M05、M06、M07、M09，B）

> AI 接口必须遵守统一外层结构；AI 输出默认是草稿/候选，不自动视为用户确认。

### 5.1 准备稿对象

```json
{
  "preparation_id": "prep_xxx",
  "meeting_id": "mtg_xxx",
  "summary": "会议背景摘要……",
  "checklist": ["确认本周里程碑", "询问接口联调风险"],
  "status": "draft",
  "version": 1,
  "created_at": "2026-10-01T09:20:00+08:00",
  "updated_at": "2026-10-01T09:20:00+08:00"
}
```

- `checklist` 为字符串数组；`status`：`generating` / `draft` / `confirmed` / `failed`。

### 5.2 生成准备稿 `POST /api/v1/meetings/{meeting_id}/prepare`

```json
{ "include_history": true, "user_goal": "确认本周里程碑和待解决风险" }
```

可选字段：
- `model`（string）：覆盖本次生成使用的模型名，来自模型配置弹窗中服务商预设的常用模型清单；模型名是否有效由服务商 API 判定（无效时返回调用错误）；
- `template_id`（string）：套用输出模板（内置或本人自定义，见 5.16a 会议模板），模板结构文本作为独立段注入生成提示词的 user 消息（不进 system，见 `ai-design.md 七`）；不存在或越权返回 `404 RESOURCE_NOT_FOUND`。

响应 `200`：准备稿对象（`status = draft`）。同步完成；超时返回统一错误。`include_history=true` 时在用户授权范围内加入有限历史材料；`false` 时只使用当前会议材料。
每次生成**新增一条**准备稿记录；对某条记录的编辑原地更新并 `version` 递增（`ai-design.md 八.1`）。

> **异步模式（`ASYNC_JOBS_ENABLED=true`，默认）**：先同步校验归属与模型配置（404/400 仍同步返回），随后落一条 `status=generating` 占位稿并返回 `202` + `data = { "job": … }`（`job_type=preparation_generate`，`resource_id` 为占位稿 id，见 `api.md 1.9`）；任务结束把占位稿转 `draft`，失败转 `failed`（任务 `error_code` 同步写入）。前端轮询任务后取准备稿详情。开关关闭时按上述 `200` 同步返回。

### 5.3 准备稿列表 `GET /api/v1/meetings/{meeting_id}/preparations`

响应 `200`：分页结构，按 `created_at` 倒序。

### 5.4 准备稿详情 `GET /api/v1/preparations/{preparation_id}`

响应 `200`：准备稿对象。

### 5.5 编辑准备稿 `PATCH /api/v1/preparations/{preparation_id}`

可更新字段：`summary`、`checklist`。响应 `200` 为更新后对象，`version` 递增。状态流转见 5.6。

### 5.6 确认准备稿 `POST /api/v1/preparations/{preparation_id}/confirm`

无请求体。将准备稿由 `draft` 置为 `confirmed`，响应 `200` 为更新后的准备稿对象（`status = confirmed`）。

- 幂等：已确认的准备稿重复调用返回同样结果，`version` 不再递增。
- 仅准备稿所属会议的拥有者可操作；不存在或越权统一 `404 RESOURCE_NOT_FOUND`。

### 5.7 会议问答 `POST /api/v1/meetings/{meeting_id}/chat`

```json
{ "question": "上次会议决定了什么？", "context_scope": "current_meeting", "include_sources": true }
```

可选字段 `model`（string）：覆盖本次对话使用的模型名，来自服务商预设的常用模型清单；模型名是否有效由服务商 API 判定。

可选字段 `mode`（string，默认 `plan`）：`plan` 先讨论/规划；`build` 基于资料直接产出可交付文件（结构化 Markdown，随响应 `file` 字段返回，由前端转 DOCX 下载并可保存为会议资料/写入本地文件夹）。

`context_scope`：`current_meeting`（默认）/ `current_and_history` / `knowledge_base`。它只控制检索范围，不授予权限：
- `current_meeting`：当前会议材料；
- `current_and_history`：当前用户全部会议材料，但会议记录仍只取当前会议最近记录（有限条数/长度）；
- `knowledge_base`：仅当前用户个人知识库，不读取会议材料或会议记录。

响应 `200`：

```json
{
  "status": "success",
  "data": {
    "answer": "根据已有会议材料，上次会议决定……",
    "sources": [
      { "meeting_id": "mtg_old", "material_id": "mat_old", "record_id": null, "document_id": null, "document_name": null, "excerpt": "相关原文片段", "origin": "material", "url": null, "title": null },
      { "meeting_id": "mtg_xxx", "material_id": null, "record_id": "rec_xxx", "document_id": null, "document_name": null, "excerpt": "当前会议记录片段", "origin": "record", "url": null, "title": null },
      { "meeting_id": null, "material_id": null, "record_id": null, "document_id": "kdoc_xxx", "document_name": "项目手册.pdf", "excerpt": "知识库原文片段", "origin": "material", "url": null, "title": null },
      { "meeting_id": null, "material_id": null, "record_id": null, "document_id": null, "document_name": null, "excerpt": "联网检索片段……", "origin": "web", "url": "https://example.com/a", "title": "页面标题" }
    ],
    "insufficient_evidence": false,
    "file": null
  }
}
```

- `sources` 可为空数组，不得伪造引用；`origin` 标识来源类别：`material`（会议材料/知识库，`material_id` 或 `document_id` 有值）、`record`（当前会议记录，`record_id` 有值）、`web`（联网检索，`url`/`title` 有值）。
- 证据不足时 `insufficient_evidence = true`，并进入**两段式联网补救**：先在回答开头告知「你的会议资料中未找到相关证据」，再基于联网检索片段作答（`origin=web` 来源）；联网关闭、无结果或失败时回退为原拒答文案，绝不裸报错。联网仅发生在答案层，不改变检索层阈值/Judge 口径；问题文本会发送至所配置的搜索服务（默认 cn.bing.com）。
- `mode=build` 且证据充分时 `file` 返回 `{ "filename": "xxx.md", "content": "Markdown 正文" }`；`plan` 模式或证据不足时为 `null`。

### 5.7a 流式问答（SSE）`POST /api/v1/meetings/{meeting_id}/chat/stream`

与 5.7 同一请求体（`question` / `context_scope` / `include_sources` / `model` / `mode`），**仅支持 `mode=plan`**：传 `mode=build` 返回 `422 VALIDATION_ERROR`（Build 继续走同步 5.7）。检索、归属校验与模型解析在返回流之前同步完成（404/400/402 等错误在此阶段以普通 JSON 错误体返回）。

**该端点不使用统一信封**（直接输出 SSE 事件流）。响应头：

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

事件协议（每帧 `event:` + `data:`（JSON）+ 空行）：

```
event: meta
data: {"insufficient_evidence":false,"sources":[{ ...同 5.7 的 source 字段... }],"model":"gpt-4o-mini"}

event: delta
data: {"text":"增量文本"}

event: done
data: {"answer":"完整文本","usage":{"input":123,"output":45},"latency_ms":2345}

event: error
data: {"status":"error","error_code":"MODEL_TIMEOUT","message":"模型响应超时","retryable":true}
```

- 顺序保证：**`meta` 先于首个 `delta`**（服务端预取首增量后才开始下发）；`include_sources=false` 时 `sources` 为空数组；`insufficient_evidence`、拒答文案与 5.7 同口径。
- `done.usage` 为服务商返回的 token 用量（拿不到时为 `null`）；`latency_ms` 为从受理到下发 `done` 的耗时。
- 错误两段式：**首增量前**的错误（归属/检索/模型配置/首 token 失败）返回普通 JSON 错误体（HTTP 状态码 + `error_code`，Content-Type 为 `application/json`）；**首增量后**的错误下发 `event: error` 后关闭连接，**不下发 `done`**。
- 心跳：无增量时每 `SSE_HEARTBEAT_SECONDS`（默认 15 秒）发送注释行 `: ping`，防止代理断开空闲连接。首增量前处于预取阶段（等待模型首个 token），该时段内没有心跳——这是「首 token 前错误走 JSON」的既定取舍。
- 客户端断开：服务端停止读取上游并关闭连接，不写半条 assistant 消息（对应前端 `AbortController` 取消）。
- 兼容开关：`SSE_CHAT_ENABLED=false` 时该端点返回 `404 RESOURCE_NOT_FOUND`，前端回退同步 5.7；开关与心跳见 `docker/.env.example`。
- 可观测：`GET /api/v1/metrics` 计数器 `chat_stream_total`（成功进入流的次数）、`chat_stream_error_total`（首增量前 JSON 错误 + 流内 error 事件）与窗口 `chat_stream_first_token_ms`（首 token 延迟，见 1.8）。
- 限流：与 5.7 同属 AI 组（按用户每分钟 `RATE_LIMIT_AI_PER_MINUTE`）。

### 5.8 整理记录 `POST /api/v1/meetings/{meeting_id}/organize`

```json
{ "record_ids": ["rec_xxx"], "task": "organize", "style": "分点输出" }
```

- `task`（可选，默认 `organize`）：`organize` 整理记录 / `summary` 提炼要点 / `brief` 简短摘要 / `polish` 修正口误建议。
- 输入源三级回退：`text`（直接传文本，≤20000 字）> `audio_id`（使用该音频的转写文本）> `record_ids`（为空数组时回退到最近 20 条 ≤8000 字记录）；三者均无内容返回 `422 VALIDATION_ERROR`。
- `instruction`（可选，≤2000 字）：用户附加要求，注入设计好的任务提示词（user 消息追加「用户补充要求：…」节）；为空时不追加，system 提示词不受影响。
- `model`（可选）：覆盖本次任务使用的模型，须已在模型配置中登记。
- `style`（可选）：风格要求，对 `organize` / `brief` 生效。

响应 `200`：

```json
{
  "status": "success",
  "data": {
    "task": "organize",
    "organized_content": "整理后的内容……",
    "structured": null,
    "source_record_ids": ["rec_xxx"]
  }
}
```

- `summary` / `polish` 任务：服务端经结构化管线（解析预处理 → schema + 业务字段校验 → 1 次修复重试，`ai-design.md 3.3`）写入 `structured`（`summary` 为四段结构对象，`polish` 为修改建议数组）；修复重试后仍失败时 `structured = null`，`organized_content` 返回首次尝试的原始文本供前端降级展示（接口保持 200），校验通过时 `organized_content` 为空字符串。
- `organize` / `brief` 任务：`structured` 恒为 `null`，正文在 `organized_content`。
- `polish` 的 `structured` 为建议清单，由用户逐条确认后由前端写回转写文本（`PATCH /audio/{id}`），后端不直接改写。

> 该结果为临时整理，不落库（无对应表）；不覆盖原始记录与转写文本。

### 5.9 纪要对象

```json
{
  "minutes_id": "min_xxx",
  "meeting_id": "mtg_xxx",
  "content": "会议纪要草稿……",
  "status": "draft",
  "version": 1,
  "template": "standard",
  "source_record_ids": ["rec_xxx"],
  "source_material_ids": ["mat_xxx"],
  "created_at": "2026-10-01T10:00:00+08:00",
  "updated_at": "2026-10-01T10:00:00+08:00"
}
```

`status`：`draft` / `confirmed`。
`template`：`standard` / `concise` / `task_list` / `custom`（`custom` 表示生成时套用了会议模板，见 5.10 `template_id`）。
`source_record_ids` 与 `source_material_ids` 记录实际参与生成的记录和材料。

### 5.10 生成纪要 `POST /api/v1/meetings/{meeting_id}/minutes/generate`

```json
{
  "record_ids": ["rec_xxx"],
  "include_action_items": true,
  "include_materials": true,
  "template": "standard"
}
```

可选字段 `template_id`（string）：套用输出模板（内置或本人自定义，见 5.16a），优先于 `template`；模板结构文本作为独立段注入生成提示词的 user 消息（不进 system，见 `ai-design.md 七`），生成结果的 `template` 字段记为 `custom`。模板不存在或越权返回 `404 RESOURCE_NOT_FOUND`。

- `include_materials` 默认 `true`；为 `true` 时融合当前会议资料（最多 10 份、合计约 12000 字符）和记录标记。
- `template` 省略时优先使用记忆中心的 `preferred_minutes_template`，未设置则 `standard`：
  - `standard`：标准纪要；
  - `concise`：简洁记录，仅保留关键结论、决议和待办；
  - `task_list`：任务清单，列出负责人和截止时间，未提及则写“未指定”。
- `record_ids` 为空时使用当前会议最近记录（最多 100 条）；标记只从实际参与生成的记录中提取。
- 响应 `201`：纪要对象（`status = draft`）。
- 每次生成**新增一条**纪要记录，不覆盖已确认纪要；编辑原地更新并 `version` 递增，确认置 `confirmed`（`ai-design.md 八.4`）。
- **异步模式（`ASYNC_JOBS_ENABLED=true`，默认）**：先同步校验归属/记录/模型配置（404/400 同步返回），LLM 生成交后台任务，返回 `202` + `data = { "job": … }`（`job_type=minutes_generate`，`resource_id` 为 `null`——纪要到任务结束才创建，见 `api.md 1.9`）；前端轮询任务后刷新纪要列表。开关关闭时按上述 `201` 同步返回。

### 5.11 纪要列表 `GET /api/v1/meetings/{meeting_id}/minutes`

响应 `200`：分页结构，按 `created_at` 倒序。

### 5.12 纪要详情 `GET /api/v1/minutes/{minutes_id}`

响应 `200`：纪要对象。

### 5.13 编辑纪要 `PATCH /api/v1/minutes/{minutes_id}`

可更新字段：`content`。响应 `200` 为更新后对象，`version` 递增。

### 5.14 确认纪要 `POST /api/v1/minutes/{minutes_id}/confirm`

响应 `200`：返回 `status = confirmed` 的纪要对象。

### 5.15 提取行动项 `POST /api/v1/meetings/{meeting_id}/action-items/extract`

```json
{ "record_ids": ["rec_xxx"] }
```

响应 `200`：

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "action_id": "act_xxx",
        "meeting_id": "mtg_xxx",
        "content": "完成接口联调",
        "assignee": "张三",
        "due_date": "2026-10-05",
        "status": "pending_confirmation",
        "source": { "record_id": "rec_xxx", "excerpt": "张三负责在下周一前完成接口联调" }
      }
    ]
  }
}
```

AI 提取默认 `pending_confirmation`，不得自动转任务。
- 重复提取可能产生重复候选，MVP 不做去重；转任务以 `action_id` 唯一保证幂等。

### 5.16 提取问题 `POST /api/v1/meetings/{meeting_id}/issues/extract`

```json
{ "record_ids": ["rec_xxx"] }
```

响应 `200`：

```json
{
  "status": "success",
  "data": {
    "items": [
      { "issue_id": "iss_xxx", "meeting_id": "mtg_xxx", "description": "接口联调时间可能延期", "status": "open", "follow_up": "确认依赖接口完成时间", "source": { "record_id": "rec_xxx" } }
    ]
  }
}
```

### 5.16a 会议模板（M02 扩展，B）

用于会前准备稿与纪要生成的输出模板。内置模板由项目代码提供（不入库，覆盖会前摘要/议程/发言稿与会后纪要/记录及通用简报，含 `category` 分类），自定义模板按用户隔离存储，支持文件上传与纯文本创建。

模板对象：

```json
{
  "template_id": "tpl_xxx",
  "name": "产品评审模板",
  "description": "用于产品评审会",
  "category": "会后",
  "source": "custom",
  "file_name": "review.md",
  "created_at": "2026-10-29T10:00:00+08:00",
  "content_preview": "1. 评审结论；2. 问题清单"
}
```

- `source`：`builtin`（内置，`created_at`/`file_name` 为 `null`）/ `custom`（本人创建或上传）。
- `category`：`会前` / `会后` / `通用`，可空。
- `content_preview`：模板正文前 60 字符（压平空白），供卡片缩略图展示；列表响应不包含模板正文，正文通过详情接口获取。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meeting-templates` | 模板列表（内置 + 本人自定义，内置在前） |
| POST | `/api/v1/meeting-templates` | 上传模板（multipart：`file` 必填，`name`/`description`/`category` 可选） |
| POST | `/api/v1/meeting-templates/text` | 按文本创建模板（JSON：`name`/`content_text` 必填，`description`/`category` 可选） |
| POST | `/api/v1/meeting-templates/generate` | AI 生成模板草稿（JSON：`description` 必填；返回候选结果不入库） |
| GET | `/api/v1/meeting-templates/{template_id}` | 模板详情（含 `content_text` 正文） |
| DELETE | `/api/v1/meeting-templates/{template_id}` | 删除本人自定义模板 |

- 文本创建与上传共用约束：名称 ≤100 字符、描述 ≤255 字符、内容 ≤20000 字符、分类仅限 `会前`/`会后`/`通用`；违规返回 `422 VALIDATION_ERROR`。
- 上传约束：仅支持 `DOCX` / `TXT` / `MD`；大小沿用全局上传限制（20MB）；内容解析失败返回 `422 FILE_PARSE_FAILED`，类型不支持返回 `415 FILE_TYPE_NOT_SUPPORTED`，超限返回 `413 FILE_TOO_LARGE`。
- AI 生成：按用途模型路由（`minutes` 用途）调用 LLM，返回 `{name, description, category, content_text}` 草稿候选，**不入库**；用户确认后通过 `text` 端点保存。未配置模型返回 `400 MODEL_CONFIG_REQUIRED`，模型异常沿用统一错误码。
- 权限：内置模板人人可读、不可删除；自定义模板仅本人可见/可删，越权统一 `404 RESOURCE_NOT_FOUND`。
- 生成联动：`prepare`（5.2）与 `minutes/generate`（5.10）接受可选 `template_id`，模板正文注入提示词 user 消息段（不进 system）；自定义模板不可用或已删除时按原逻辑返回 `404`。
- 默认模板：记忆中心 `preferred_minutes_template`（5.15）支持内置枚举值或模板清单中的模板 id；非枚举值时生成自动注入该模板正文并记 `template=custom`。


## 六、行动项与个人任务（M07、M08，A）

### 6.1 行动项对象

```json
{
  "action_id": "act_xxx",
  "meeting_id": "mtg_xxx",
  "content": "完成接口联调",
  "assignee": "张三",
  "due_date": "2026-10-05",
  "status": "confirmed",
  "source": { "record_id": "rec_xxx", "excerpt": "张三负责在下周一前完成接口联调" },
  "created_at": "2026-10-01T10:05:00+08:00",
  "updated_at": "2026-10-01T10:05:00+08:00"
}
```

`status`：`pending_confirmation` / `confirmed` / `converted` / `cancelled`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings/{meeting_id}/action-items` | 行动项列表 |
| GET | `/api/v1/action-items/{action_id}` | 行动项详情 |
| PATCH | `/api/v1/action-items/{action_id}` | 编辑行动项 |
| DELETE | `/api/v1/action-items/{action_id}` | 删除行动项（未转任务时）|
| POST | `/api/v1/action-items/{action_id}/confirm` | 确认行动项 |
| POST | `/api/v1/action-items/{action_id}/convert-to-task` | 转为任务 |

- 编辑可更新 `content`、`assignee`、`due_date`。
- 确认：幂等成功。
- 删除：若已转换为任务，返回 `409 BUSINESS_RULE_VIOLATION`。

### 6.2 转任务 `POST /api/v1/action-items/{action_id}/convert-to-task`

```json
{ "title": "完成接口联调", "due_date": "2026-10-05" }
```

`title` 必填，`due_date` 可空。仅 `confirmed` 行动项可转换。响应 `201`：

```json
{
  "status": "success",
  "data": {
    "task_id": "tsk_xxx",
    "user_id": "usr_xxx",
    "meeting_id": "mtg_xxx",
    "action_id": "act_xxx",
    "title": "完成接口联调",
    "status": "todo",
    "due_date": "2026-10-05",
    "created_at": "2026-10-01T10:10:00+08:00",
    "updated_at": "2026-10-01T10:10:00+08:00"
  }
}
```

- 重复转换幂等：返回已存在任务（HTTP `200`）。
- 转换后行动项状态更新为 `converted`。

### 6.3 任务对象

```json
{
  "task_id": "tsk_xxx",
  "user_id": "usr_xxx",
  "meeting_id": "mtg_xxx",
  "action_id": "act_xxx",
  "title": "完成接口联调",
  "status": "todo",
  "due_date": "2026-10-05",
  "created_at": "2026-10-01T10:10:00+08:00",
  "updated_at": "2026-10-01T10:10:00+08:00"
}
```

`status`：`todo` / `in_progress` / `completed` / `cancelled`。允许流转：`todo ↔ in_progress`；`todo`、`in_progress` 可直接转入 `completed`；`completed` 可撤回 `todo`（归档撤回）；未完成任务可转入 `cancelled`，`cancelled` 为终态不可回退。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/tasks` | 新建个人任务（`201`） |
| GET | `/api/v1/tasks` | 任务列表 |
| GET | `/api/v1/tasks/{task_id}` | 任务详情 |
| PATCH | `/api/v1/tasks/{task_id}` | 修改任务 |
| POST | `/api/v1/tasks/{task_id}/cancel` | 取消任务 |

- 新建：请求体 `{ "title": 必填 ≤255, "due_date": 可选日期 }`；默认 `status = todo`，不关联会议（`meeting_id` / `action_id` 为 `null`）。
- 列表查询参数：`page`、`page_size`、`status`（MVP）；`keyword`、`due_before`、`due_after` 为后续增强。
- 编辑可更新 `title`、`due_date`、`status`（后端校验状态流转，非法流转返回 `409 BUSINESS_RULE_VIOLATION`）。
- 取消：幂等成功，返回 `status = cancelled`；已完成任务不可取消（`409`）。

## 七、未解决问题（M09，A）

问题对象：

```json
{
  "issue_id": "iss_xxx",
  "meeting_id": "mtg_xxx",
  "description": "接口联调时间可能延期",
  "status": "open",
  "follow_up": "确认依赖接口完成时间",
  "source": { "record_id": "rec_xxx" },
  "created_at": "2026-10-01T10:20:00+08:00",
  "updated_at": "2026-10-01T10:20:00+08:00"
}
```

`status`：`open` / `resolved` / `cancelled`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings/{meeting_id}/issues` | 问题列表 |
| PATCH | `/api/v1/issues/{issue_id}` | 修改问题 |

- 编辑可更新 `description`、`status`、`follow_up`。
- AI 提取接口见 §5.16（负责人 B）；问题 CRUD/状态（本页）负责人 A。

## 八、接口联调顺序

| 批次 | 接口范围 | 参与成员 |
| --- | --- | --- |
| 第一批 | 认证、健康检查、会议 CRUD | A、C |
| 第二批 | 材料上传、材料状态、记录 CRUD | A、B、C |
| 第三批 | 模型调用、RAG、会前准备 | A、B、C |
| 第四批 | 会议问答、纪要生成、行动项/问题提取 | A、B、C |
| 第五批 | 行动项确认、任务 CRUD、问题管理 | A、B、C |
| 第六批 | 异常、权限、部署和端到端测试 | 全员 |

## 九、变更规则

- 接口字段、状态值、错误码或路径变更必须先更新本文件，再更新实现。
- 每个 PR 应说明：新增/修改的接口、请求响应变化、是否影响其他成员、是否需要数据库迁移。
- `[扩展]` 接口不在 MVP 范围。
