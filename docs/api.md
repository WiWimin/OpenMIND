# API 契约

本文件是前端、后端与 AI 模块的共同接口基线，也是接口的唯一事实来源。运行期以 FastAPI 自动生成的 OpenAPI 文档为准；设计与实现冲突时先更新本文件。

> 状态：MVP 设计基线。`[提案]` 表示本次新增、需团队确认后实现的接口；`[扩展]` 表示非 MVP、先定义结构但不实现。

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
| `FILE_PARSE_FAILED` | 422 | 文件无法解析（原因见 `details.reason`，见下） | 通常否 |
| `MODEL_TIMEOUT` | 504 | 模型调用超时 | 是 |
| `MODEL_OUTPUT_INVALID` | 502 | 模型输出无法解析 | 视情况 |
| `MODEL_CONFIG_INVALID` | 400 | 模型配置校验失败（密钥无效/维度不符/额度不足等） | 否 |
| `MODEL_CONFIG_REQUIRED` | 400 | 用户未配置模型 Key（BYOK） | 否 |
| `MODEL_QUOTA_EXCEEDED` | 402 | 模型额度不足 | 否 |
| `RATE_LIMITED` | 429 | 请求频率超过限制 | 是 |
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

### 1.8 健康检查（豁免信封）

以下探针端点不套用 `{ "status": "success", "data": ... }` 信封，直接返回探针结果：

| 方法 | 路径 | 成功响应 |
| --- | --- | --- |
| GET | `/health` | `{ "status": "ok" }` |
| GET | `/api/v1/health/db` | `{ "status": "ok", "database": "up" }`（数据库不可用返回 503 统一错误体） |

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

### 2.5 模型配置（用户自带 BYOK，M04，B）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/me/settings/model` | 读取当前生效的模型配置（密钥脱敏） |
| PUT | `/api/v1/me/settings/model` | 保存/替换模型配置（probe 校验后加密存库） |
| PUT | `/api/v1/me/settings/model/purposes` | 保存按用途覆盖的模型名 |
| DELETE | `/api/v1/me/settings/model` | 清空自备配置，回退服务端全局 |

PUT 请求（字段可按提供方整体省略，省略即清空该提供方）：

```json
{
  "llm_api_base": "https://api.example.com/v1",
  "llm_api_key": "sk-...",
  "llm_model": "model-name",
  "embedding_api_base": "https://api.example.com/v1",
  "embedding_api_key": "sk-...",
  "embedding_model": "text-embedding-1024"
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
    "embedding_api_key_masked": "sk-...abcd",
    "embedding_source": "user",
    "embedding_dim": 1024
  }
}
```

规则：
- 密钥 `Fernet` 加密存库，永不明文返回；`_masked` 仅展示前后缀。
- `_masked` 仅在来源为 `user` 时返回值；`global` / `none` 返回空字符串，避免向普通用户泄露服务端全局密钥片段。
- 保存时 probe 实测：Embedding 必须返回 **1024** 维向量、LLM 需能生成；失败返回 `400 MODEL_CONFIG_INVALID`。
- 保存前校验 `api_base`：默认只允许 HTTPS 公网地址，拒绝本机/私有/保留地址、URL 内嵌凭证和 query/fragment；自建本地模型需显式开启 `ALLOW_PRIVATE_MODEL_ENDPOINTS=true`。
- 默认 `ALLOW_GLOBAL_FALLBACK=false`：未配置 BYOK 的用户不会自动使用服务端全局 Key；AI 接口返回 `400 MODEL_CONFIG_REQUIRED`。
- 仅当 `ALLOW_GLOBAL_FALLBACK=true` 时按“用户配置 > 服务端全局（`docker/.env`）”回退。
- `llm_source` / `embedding_source` 表示该提供方生效来源：`user`（用户自备）、`global`（服务端全局）、`none`（未配置）；两者独立判定。
- `llm_purpose_models` 返回已保存的用途模型覆盖；未知用途或空模型名在写入时返回 `422`，未配置大模型时写入返回 `400 MODEL_CONFIG_INVALID`。
- 轮换 `SECRET_KEY` 时设置 `SECRET_KEY_PREVIOUS` 为旧值以解密既有密文；新写入使用当前 `SECRET_KEY`。确认全部配置已重新保存后可移除旧值。
- 无法解密既有密文时返回 `400 MODEL_CONFIG_INVALID`；可调用 `DELETE /me/settings/model` 清除后重新配置。
- 模型额度不足返回 `402 MODEL_QUOTA_EXCEEDED`；密钥无效/配置错误返回 `400 MODEL_CONFIG_INVALID`。

### 2.6 个人知识库

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/knowledge/documents` | 上传 PDF / DOCX / TXT，解析、分块并建立向量索引 |
| GET | `/api/v1/knowledge/documents` | 当前用户知识库文档分页列表 |
| GET | `/api/v1/knowledge/documents/{document_id}` | 文档详情 |
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
  "created_at": "2026-10-01T09:00:00+08:00"
}
```

`processing_status`：`uploaded` / `processing` / `processed` / `failed`。

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
- 解析失败返回 `201`，对象 `processing_status=failed` 并带 `parse_error`；不支持的类型返回 `415 FILE_TYPE_NOT_SUPPORTED`。
- 删除文档同步删除分块与向量索引，删除后不得再被检索。
- 知识库检索当前作为独立接口，不自动混入会议问答；后续接入时需显式选择范围。

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
  "created_at": "2026-10-01T09:10:00+08:00"
}
```

- `processing_status`：`uploaded` / `processing` / `processed` / `failed`。
- 允许 `pdf` / `docx` / `txt`；单文件 ≤ `MAX_UPLOAD_MB`（默认 20MB）。
- 不暴露 `storage_key`、文件系统路径与未脱敏异常。

### 4.2 上传材料 `POST /api/v1/meetings/{meeting_id}/materials`

请求类型：`multipart/form-data`。字段：`file`（必填，单个）、`source`（可选）、`material_type`（可选，缺省由后端按扩展名推断；对应响应与数据库的 `type`）。

响应 `201`：材料对象。当前为同步解析/索引，成功时 `processing_status = processed`；解析或索引失败时返回 `failed` 并写入 `parse_error`，文件类型不支持 `415`，过大 `413`。

> 上传路径的解析失败以 `processing_status=failed` + `parse_error` 表达，不返回 `422 FILE_PARSE_FAILED`；后者用于解析层错误语义说明，不是上传接口的响应。

### 4.3 材料列表 `GET /api/v1/meetings/{meeting_id}/materials` [提案]

查询参数：`page`、`page_size`。响应 `200`：分页结构，`items` 为材料对象数组，按 `created_at` 倒序。

### 4.4 材料详情 `GET /api/v1/materials/{material_id}`

响应 `200`：材料对象（含 `parse_error`，失败时用于前端提示）。

### 4.5 删除材料 `DELETE /api/v1/materials/{material_id}`

响应 `200`：`{ "status": "success", "data": { "deleted": true, "material_id": "mat_xxx" } }`。
删除后相关分块与向量索引同步清理，RAG 不得再检索到；引用该材料的 `meeting_records.source_material_id` 置空。

### 4.6 音频转写 `POST /api/v1/materials/{material_id}/transcribe` [扩展]

非 MVP。一旦实现必须固定同步或 `202` 契约并写入 OpenAPI。

### 4.7 记录对象

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

### 4.8 新增记录 `POST /api/v1/meetings/{meeting_id}/records`

```json
{ "content": "讨论记录正文", "record_type": "manual", "marker_type": "decision" }
```

`content` 必填；`marker_type` 可选。响应 `201` 为记录对象。

### 4.9 记录列表 `GET /api/v1/meetings/{meeting_id}/records`

查询参数：`page`、`page_size`。响应 `200`：分页结构。

### 4.10 编辑记录 `PATCH /api/v1/records/{record_id}`

可更新字段：`content`、`marker_type`。传 `marker_type: null` 清除标记；归档会议不可修改。响应 `200` 为更新后记录对象。

### 4.11 删除记录 `DELETE /api/v1/records/{record_id}` [提案]

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

响应 `200`：准备稿对象（`status = draft`）。同步完成；超时返回统一错误。`include_history=true` 时在用户授权范围内加入有限历史材料；`false` 时只使用当前会议材料。
每次生成**新增一条**准备稿记录；对某条记录的编辑原地更新并 `version` 递增（`ai-design.md 八.1`）。

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
      { "meeting_id": "mtg_old", "material_id": "mat_old", "record_id": null, "document_id": null, "document_name": null, "excerpt": "相关原文片段" },
      { "meeting_id": "mtg_xxx", "material_id": null, "record_id": "rec_xxx", "document_id": null, "document_name": null, "excerpt": "当前会议记录片段" },
      { "meeting_id": null, "material_id": null, "record_id": null, "document_id": "kdoc_xxx", "document_name": "项目手册.pdf", "excerpt": "知识库原文片段" }
    ],
    "insufficient_evidence": false
  }
}
```

- `sources` 可为空数组，不得伪造引用；来源可以是会议材料分块（`material_id` 有值）、当前会议记录（`record_id` 有值，`material_id` 为 `null`）或个人知识库分块（`document_id` 有值，`meeting_id`/`material_id` 为 `null`）。
- 证据不足时 `insufficient_evidence = true`。

### 5.8 整理记录 `POST /api/v1/meetings/{meeting_id}/organize`

```json
{ "record_ids": ["rec_xxx"], "style": "structured" }
```

建议 MVP 要求显式传 `record_ids`。响应 `200`：

```json
{ "status": "success", "data": { "organized_content": "整理后的内容……", "source_record_ids": ["rec_xxx"] } }
```

> 该结果为临时整理，不落库（无对应表）。

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
`template`：`standard` / `concise` / `task_list`。
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

- `include_materials` 默认 `true`；为 `true` 时融合当前会议资料（最多 10 份、合计约 12000 字符）和记录标记。
- `template` 默认 `standard`：
  - `standard`：标准纪要；
  - `concise`：简洁记录，仅保留关键结论、决议和待办；
  - `task_list`：任务清单，列出负责人和截止时间，未提及则写“未指定”。
- `record_ids` 为空时使用当前会议最近记录（最多 100 条）；标记只从实际参与生成的记录中提取。
- 响应 `201`：纪要对象（`status = draft`）。
- 每次生成**新增一条**纪要记录，不覆盖已确认纪要；编辑原地更新并 `version` 递增，确认置 `confirmed`（`ai-design.md 八.4`）。

### 5.11 纪要列表 `GET /api/v1/meetings/{meeting_id}/minutes` [提案]

响应 `200`：分页结构，按 `created_at` 倒序。

### 5.12 纪要详情 `GET /api/v1/minutes/{minutes_id}` [提案]

响应 `200`：纪要对象。

### 5.13 编辑纪要 `PATCH /api/v1/minutes/{minutes_id}` [提案]

可更新字段：`content`。响应 `200` 为更新后对象，`version` 递增。

### 5.14 确认纪要 `POST /api/v1/minutes/{minutes_id}/confirm` [提案]

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
| GET | `/api/v1/action-items/{action_id}` | 行动项详情 [提案] |
| PATCH | `/api/v1/action-items/{action_id}` | 编辑行动项 |
| DELETE | `/api/v1/action-items/{action_id}` | 删除行动项（未转任务时）[提案] |
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

`status`：`todo` / `in_progress` / `completed` / `cancelled`。允许流转：`todo → in_progress → completed`；未完成任务可转入 `cancelled`，终态不可回退。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/tasks` | 任务列表 |
| GET | `/api/v1/tasks/{task_id}` | 任务详情 |
| PATCH | `/api/v1/tasks/{task_id}` | 修改任务 |
| POST | `/api/v1/tasks/{task_id}/cancel` | 取消任务 |

- 列表查询参数：`page`、`page_size`、`status`（MVP）；`keyword`、`due_before`、`due_after` 为后续增强。
- 编辑可更新 `title`、`due_date`、`status`（后端校验状态流转）。
- 取消：幂等成功，返回 `status = cancelled`。

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
- `[提案]` 接口需团队确认后从提案转为正式；`[扩展]` 接口不在 MVP 范围。
