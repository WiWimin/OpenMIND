# AI 能力层设计（ai-design.md）

> **文档定位**：定义 OpenMIND 中 AI 调用、文件解析、Embedding、RAG 检索、Prompt 管理、超时重试、幂等与失败补偿的实现级设计。它是 `backend/app/ai/` 的唯一事实来源。
>
> **不定义**：业务 CRUD 的请求/响应（见 `api.md`）、表结构（见 `database.md`）。AI 只负责生成候选结果与检索，不自行决定任务/状态的业务流转。

## 一、范围与原则

适用模块：M03（解析）、M04（AI 基础/RAG）、M05（会前准备）、M06（问答）、M07（纪要/行动项提取）、M09（问题提取）。

原则：

1. **候选与确认分离**：AI 输出一律是草稿/候选，落库状态为 `draft` 或 `pending_confirmation`，必须经用户确认（`api.md`）。
2. **原始数据不被覆盖**：解析文本、记录、材料原文件分别存储。
3. **权限先行**：检索必须先按当前用户限定范围，禁止全库相似度检索后再过滤。
4. **可追溯**：生成结果须能追溯到来源记录/分块（`source_record_ids`、`sources`、`source_record_id`）。
5. **密钥服务端化**：LLM/Embedding 密钥来自「用户自带配置」（`/me/settings/model`，Fernet 加密存库，永不明文返回前端）或「服务端环境变量」，绝不下发明文。

## 二、能力层结构

```text
backend/app/ai/
├── llm/          # 大模型调用（超时、重试、结构化输出）
├── embeddings/   # 文本向量化
├── rag/          # 权限内检索
├── prompts/      # Prompt 模板集中管理
├── parsers/      # 文件解析（pdf/docx/txt）——已由 M03 PR 落地
├── preparation/  # 会前准备生成
├── minutes/      # 纪要生成
├── extraction/   # 行动项/问题提取
└── chat/         # 问答编排（RAG + Prompt）
```

- 各子包对外只暴露 `service` 层函数/类；业务层（`services/`）调用它们，不直接调用底层 HTTP。
- 目录职责与模块映射见 `module-development-spec.md`。

## 三、统一 LLM 调用（`ai/llm/`）

### 3.1 客户端接口

```python
class LLMResult:
    text: str
    model: str
    usage: dict[str, int]      # {"input": int, "output": int}
    latency_ms: int

class LLMClient:
    def chat(
        self,
        messages: list[dict],          # [{"role":"system|user|assistant","content":str}]
        *,
        model: str | None = None,      # 缺省取 settings.llm_model
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout_s: float = 60,
        response_format: dict | None = None,   # {"type":"json_object"} 等
    ) -> LLMResult: ...

    def chat_json(self, messages, *, schema: type[BaseModel], **kw) -> BaseModel: ...
```

- 配置来源：`ModelConfig`（`services/model_config_service.py`），按用户解析；优先级为**用户配置 > 服务端全局**（`settings.llm_*`）。用户未配置时回退全局，全局默认为空则不兜底。
- MVP 使用**同步**调用；调用发生在请求线程内，超时转化为统一错误（见 §十）。

### 3.2 超时与重试

| 项 | 约定 |
| --- | --- |
| 单次超时 | 默认 60s（生成类可上调至 120s） |
| 重试次数 | 最多 2 次重试（共 3 次尝试） |
| 退避 | 指数：1s、3s |
| 可重试条件 | 超时、`429`、`5xx`、网络错误 |
| 不可重试 | `401/403`（密钥/权限）、`400`（请求非法） |

### 3.3 结构化输出

- 需要结构化结果的场景（准备稿、纪要、行动项、问题）使用 `chat_json` + Pydantic schema 校验。
- 校验失败或模型返回非 JSON → `MODEL_OUTPUT_INVALID`（502）。
- 严禁把模型原始异常或提示词返回给前端。

### 3.4 记录与可观测

- 每次调用记录：模型名、`usage`、`latency_ms`、成功/失败（日志或后续 `ai_call_logs`）。

### 3.5 模型配置来源（用户自带 BYOK）

- 每个用户可通过 `PUT /api/v1/me/settings/model` 自备 LLM / Embedding 配置（`api_base` + `api_key` + `model`）。
- 密钥 `Fernet` 加密存库（`user_model_configs`），密钥由服务端 `SECRET_KEY` 派生；`GET` 仅返回脱敏值，绝不回显明文。来源为 `global`/`none` 时 `_masked` 为空，不向用户泄露全局密钥片段。
- 保存时 probe 实测校验：Embedding 必须返回 **1024** 维向量；LLM 需能正常生成；失败返回 `MODEL_CONFIG_INVALID`（400）。
- `api_base` 默认只允许 HTTPS 公网地址；拒绝本机、私有/保留 IP、URL 内嵌凭证及 query/fragment。自建本地模型需显式开启 `ALLOW_PRIVATE_MODEL_ENDPOINTS`，该开关会扩大 SSRF 面，仅限可信部署。应用层校验不能完全消除 DNS rebinding，部署侧仍应限制出站访问。
- `SECRET_KEY` 在非开发环境必须为至少 32 字符的随机值；轮换时通过 `SECRET_KEY_PREVIOUS` 保留旧密钥解密既有密文，新加密始终使用当前 `SECRET_KEY`。解密失败返回 `MODEL_CONFIG_INVALID`，用户可清除并重新保存配置。
- 默认要求用户配置 BYOK；`ALLOW_GLOBAL_FALLBACK=false` 时未配置用户返回 `MODEL_CONFIG_REQUIRED`（400），不会静默使用服务端全局 Key。仅显式开启 `ALLOW_GLOBAL_FALLBACK=true` 时按“用户配置 > 服务端全局”回退。
- 按用途模型：`user_model_configs.llm_purpose_models` 保存 `preparation` / `chat` / `minutes` / `extraction` 的模型名覆盖；仅覆盖模型名，API 地址与密钥沿用 LLM 基础配置。未覆盖或未设置时使用默认 `llm_model`。
- 请求级模型覆盖：会议问答（`chat`）与会前准备（`prepare`）接受可选 `model` 参数（`api.md 5.7 / 5.2`），仅允许选择已登记的模型（基础 `llm_model` 或任一用途模型，用途覆盖前收集候选集），否则返回 `MODEL_NOT_ALLOWED`（422）。API 地址与密钥仍沿用配置，不因请求切换提供方。
- 调用方必须显式传入用途：会前准备、会议问答/整理、纪要生成、行动项/问题提取分别使用对应用途；Embedding 仍使用独立 Embedding 配置。
- 模型额度不足返回 `MODEL_QUOTA_EXCEEDED`（402）；密钥无效返回 `MODEL_CONFIG_INVALID`（400）。
- Embedding 维度全局固定 1024（`document_chunks.embedding vector(1024)`），用户自备模型也必须为 1024 维。

## 四、Embedding 与文本切分（`ai/embeddings/`）

### 4.1 Embedding 客户端

```python
class EmbeddingClient:
    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]: ...
```

- 模型：`settings.embedding_model`（阿里百炼 `text-embedding-v3`）；维度：`settings.embedding_dim = 1024`。用户可自备，但维度必须为 1024（§3.5）。
- 批量：每批 ≤ 16 条；单批超时 30s；失败重试 2 次（退避 1s/3s）。
- 维度校验：返回向量长度必须等于 `settings.embedding_dim`，否则报 `INTERNAL_ERROR` 并记录。

### 4.2 切分策略

- 按字符近似切分：`chunk_size = 800`，`overlap = 120`（避免语义被截断）。
- 优先在段落/换行处切分，尽量不切断句子。
- 每块写入 `document_chunks(material_id, content, chunk_index)`，`chunk_index` 从 0 连续。
- 重解析时**先删除该材料旧分块再写入**（避免新旧混合检索）。

## 五、RAG 检索（`ai/rag/`）

### 5.1 数据与权限

- 载体：会议材料使用 `document_chunks.embedding vector(1024)`；个人知识库使用 `knowledge_chunks.embedding vector(1024)`。
- **权限范围**：会议检索必须经 `document_chunks → meeting_materials → meetings` 关联，限定 `meetings.user_id = current_user.user_id`；知识库检索必须经 `knowledge_chunks → knowledge_documents` 限定 `knowledge_documents.user_id = current_user.user_id`；禁止先全库检索再过滤。
- 只检索 `embedding IS NOT NULL` 的分块。
- 会议记录当前**不写入** `document_chunks`；问答额外使用当前会议最近记录作为受限上下文（按条数与字符上限截断）。这不是完整历史记录检索，完整记录检索需后续独立设计。

### 5.2 检索接口

```python
class RetrievedChunk:
    meeting_id: str | None
    material_id: str | None
    record_id: str | None
    document_id: str | None
    document_name: str | None
    excerpt: str
    score: float

class Retriever:
    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",   # current_meeting | current_and_history | knowledge_base
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]: ...
```

- `scope=current_meeting`：仅当前会议材料；`current_and_history`：该用户全部会议材料；`knowledge_base`：仅当前用户个人知识库，不读取会议材料或会议记录。
- 排序：当前实现为在应用层（`VectorRetriever`）按余弦**相似度**计算并排序，取前 `top_k`，低于 `min_score` 丢弃；pgvector `<=>` 余弦距离与 HNSW 索引待数据量增大后作为优化落地（`database.md 六`）。
- 无结果或全部低于阈值 → 返回空列表，由上层置 `insufficient_evidence=true`。

### 5.3 来源返回

- `api.md 五.7` 的 `sources[]` 可来自会议材料分块、当前会议记录或个人知识库分块：材料来源有 `material_id`，记录来源有 `record_id` 且 `material_id=null`，知识库来源有 `document_id`/`document_name` 且 `meeting_id`/`material_id=null`。
- 不得伪造引用；`excerpt` 必须取自命中分块或记录原文。

### 5.4 个人知识库检索

- 载体：`knowledge_chunks.embedding vector(1024)`，按 `knowledge_documents.user_id` 限定当前用户。
- 导入：PDF / DOCX / TXT → 解析 → 分块（800 字符、120 重叠）→ Embedding → 写入分块。
- 检索：查询向量与当前用户全部分块计算余弦相似度，取前 `top_k`，低于 `min_score` 丢弃。
- 返回 `document_id`、文件名、命中片段和分数；不伪造来源。
- 知识库检索默认不混入会议问答；问答中必须显式选择 `context_scope=knowledge_base`，此时不读取会议材料或会议记录，避免无关内容污染回答。
- 删除文档同步删除分块和向量，删除后不得再被检索。

### 5.5 用户记忆使用

- 来源：`user_memories`，由用户显式维护，当前不从会议内容自动提取。
- 按用途筛选：
  - 会前准备：角色、工作场景、表达偏好；
  - 纪要生成：表达偏好；未显式指定模板时使用 `preferred_minutes_template`；
  - 会议问答：表达偏好；
  - 行动项/问题提取：不使用记忆。
- 记忆只作为软偏好注入 Prompt，必须明确不得覆盖材料事实、来源、权限和业务规则。
- 用户可查看、修改、删除；删除后不再进入后续 AI 调用。

## 六、文件解析链路（M03，`ai/parsers/`）

### 6.1 处理状态机（`meeting_materials.processing_status`）

```text
uploaded → processing → processed | failed
failed → processing   （重试）
```

### 6.2 流程

```text
上传(POST materials)
  → 校验扩展名/大小（pdf/docx/txt，≤ MAX_UPLOAD_MB）
  → 落盘 storage/（storage_key 不入前端）
  → 建材料记录（默认 uploaded）
  → 同步解析/索引：processing_status=processing
      ├─ 成功：写 content，processing_status=processed，parse_error=null
      │        切分 + Embedding → document_chunks
      └─ 失败：processing_status=failed，写 parse_error（安全摘要）
```

上传接口当前同步完成处理，响应中的材料状态通常已是 `processed` 或 `failed`；`uploaded/processing` 是内部/瞬时状态，不作为上传成功的客户端契约。

- 解析层已实现（PR #4）：`parse_bytes(data, file_name) -> ParsedDocument{file_name, content, parser, metadata}`，按扩展名分发，未知/空/损坏统一抛 `ParseError`。
- `type` 取值（无点）：`pdf`/`docx`/`txt`；解析层按扩展名（带点）分发，业务层负责去点归一。

### 6.3 错误原因映射（`FILE_PARSE_FAILED` → `details.reason`）

| reason | 触发 | 来源 |
| --- | --- | --- |
| `empty_content` | 文件内容为空 | `parser_service` |
| `unsupported_format` | 扩展名不受支持 | `parser_service` |
| `no_text_layer` | PDF 无文本层（扫描件） | `pdf_parser`（PR #4） |
| `encrypted_pdf` | PDF 加密 | `pdf_parser`（PR #4） |
| `invalid_file` | 读取/格式损坏 | `parser_service` |
| `parse_failed` | 其他解析异常 | `parser_service` |

### 6.4 失败补偿与幂等

- **解析失败**：材料置 `failed` 并记录 `parse_error`，不产生分块；用户可重新上传（重试）。
- **索引失败**（解析成功但切分/Embedding 失败）：材料置 `failed`，写入原因；重试时先清理旧分块再重建。
- **未预期处理异常**：材料置 `failed` 并写入安全错误摘要，记录服务端日志，不长期停留在 `processing`。
- **删除材料**：同步删除文件对象与 `document_chunks`；`meeting_records.source_material_id` 置空（`database.md 七`）。

### 6.5 音频转写

- 支持 MP3 / WAV / M4A / WEBM，上传后同步调用 OpenAI 兼容 `/audio/transcriptions`。
- 服务端配置 `ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL`；未配置返回 `MODEL_CONFIG_REQUIRED`，不伪造转写。
- **本地 FunASR（可选）**：`docker/asr` 基于 FunASR `funasr-server`，使用 SenseVoiceSmall + FSMN-VAD，CPU 推理；Compose 服务名 `asr`，仅通过 `--profile asr` 启动，宿主机只监听 `127.0.0.1:10096`。
  - 配置：`ASR_API_BASE=http://asr:8000/v1`、`ASR_API_KEY=local-dev`（占位值，FunASR 不校验）、`ASR_MODEL=sensevoice`。
  - 启动/停止：`scripts/asr.ps1 up|down|status|logs|smoke`（Windows）或 `scripts/asr.sh`（Linux/macOS）。
  - 首次启动会下载模型（约 1GB）并加载 SenseVoice；CPU 上短音频通常在数秒内完成，长音频耗时随长度增加。
  - FunASR 服务本身无鉴权、无上传/限流；只能用于本地或受控内网，不得直接暴露公网。软件为 MIT，模型权重许可以模型页面为准。
- 状态：`uploaded → processing → transcribed | failed`；确认后 `confirmed`。
- 失败保留音频文件并记录安全错误摘要，可重试；不覆盖已有成功文本。
- 用户在确认前可修订转写；确认生成 `record_type=transcript` 的会议记录，确认幂等。
- 已确认音频不能重新转写或删除；删除未确认音频同步删除文件。
- 实时流式 ASR 不在当前范围；音频原文件不进入 RAG。

## 七、Prompt 管理（`ai/prompts/`）

- 所有模板集中在 `ai/prompts/`，按功能命名（如 `prepare.py`、`minutes.py`、`extract_action_items.py`、`chat.py`）。
- 模板函数签名：`build_xxx(context: dict) -> list[dict]`，注入会议主题、材料片段、记录等上下文。
- 不把用户原文或密钥写入日志。

## 八、AI 功能规格

> 接口契约见 `api.md 五`；以下为实现要点。

### 8.1 会前准备 `POST /meetings/{id}/prepare`
- 输入：会议信息 + 材料内容（当前会议；`include_history=true` 时加入有限历史材料）。
- 输出（结构化）：`{ summary: str, checklist: list[str] }`。
- 模板：可选 `template_id`（内置或本人自定义，见 `api.md 5.16a`），模板结构文本注入 system 提示词（`build_prepare`），仅改变输出组织方式；模板不存在或越权返回 404。
- 模型：可选 `model` 覆盖本次生成模型（校验见 §3.5）。
- 落库：**每次生成新增一条** `preparations`（`status=draft`，`version=1`）。
- 失败：置 `failed` 并返回统一错误。

### 8.2 会中问答 `POST /meetings/{id}/chat`
- 流程：按 `scope` 检索材料分块 + 当前会议最近记录（有限条数/长度）→ 组装 Prompt → LLM 生成 → 返回 `{answer, sources[], insufficient_evidence}`。
- 默认 `current_meeting`；`current_and_history` 只扩展会议材料检索范围，记录始终限当前会议。
- `knowledge_base` 仅检索当前用户个人知识库，不读取会议材料或会议记录；来源带 `document_id`/`document_name`。
- 材料、记录与知识库都为空 → `insufficient_evidence=true` 且回答明确说明无法确认。
- 不落库（问答历史非 MVP）。

### 8.3 整理记录 `POST /meetings/{id}/organize`
- 输入：显式 `record_ids`。输出 `{ organized_content, source_record_ids[] }`。不落库。

### 8.4 纪要生成 `POST /meetings/{id}/minutes/generate`
- 输入：`record_ids`、`include_action_items`、`include_materials`（默认 `true`）、`template`（可空）、`template_id`（可空）。
- 模板：`standard` 标准纪要、`concise` 简洁记录、`task_list` 任务清单；`template` 为空时使用记忆中心默认模板，未设置则 `standard`；`template_id`（会议模板，`api.md 5.16a`）优先于 `template`，模板结构文本经 `build_minutes` 注入提示词，生成结果 `template` 记为 `custom`；模板只改变输出组织方式，不降低来源与事实验证要求。
- 记忆：仅注入表达偏好；模板偏好只作为默认值，显式请求模板或 `template_id` 优先。
- 上下文：显式记录（为空时当前会议最近 100 条）+ 当前会议资料（最多 10 份、合计约 12000 字符）+ 实际参与记录上的标记（`highlight` / `decision` / `question`）。
- 资料只作背景，Prompt 明确禁止把资料中没有的信息写成会议事实；标记用于强调重点、决议和待确认问题。
- 任务清单模板中未提及负责人或截止时间时写“未指定”，不得编造。
- 输出：`minutes.content`。每次生成**新增一条** `meeting_minutes`（`status=draft`，`version=1`），记录 `template`、`source_record_ids` 和实际使用的 `source_material_ids`。
- `include_materials=false` 时不读取资料，`source_material_ids=[]`。
- 重新生成始终新增草稿，不覆盖已确认纪要；编辑（`PATCH`）原地更新并 `version` 递增；确认置 `confirmed`。

### 8.5 行动项提取 `POST /meetings/{id}/action-items/extract`
- 输出（结构化）：`[{ content, assignee?, due_date?, source_record_id?, source_excerpt? }]`。
- 落库：`action_items`，`status=pending_confirmation`。
- 不去重（重复提取可能重复）；仅 `confirmed` 可转任务。

### 8.6 问题提取 `POST /meetings/{id}/issues/extract`
- 输出（结构化）：`[{ description, follow_up?, source_record_id? }]`。
- 落库：`open_issues`，`status=open`。

## 九、幂等与失败补偿总则

| 场景 | 幂等性 | 补偿 |
| --- | --- | --- |
| 生成准备稿/纪要 | 非幂等（每次新增记录） | 失败置 `failed`，用户可重新生成 |
| 提取行动项/问题 | 非幂等（允许重复候选） | 失败返回统一错误，可重试 |
| 行动项转任务 | **幂等**：`personal_tasks.action_id` 唯一 | 重复转换返回已有任务 |
| 文件解析/索引 | 重解析先删旧分块再重建 | `failed` 可重试；材料删除清理分块 |
| 检索/问答 | 无副作用 | 无结果返回空来源 + `insufficient_evidence` |

## 十、错误码、超时与可重试

| 场景 | 错误码 | HTTP | 可重试 |
| --- | --- | ---: | --- |
| 模型超时 | `MODEL_TIMEOUT` | 504 | 是 |
| 模型输出无法解析/不符合 schema | `MODEL_OUTPUT_INVALID` | 502 | 视情况 |
| 触发限流 | `RATE_LIMITED` | 429 | 是 |
| 未配置模型（BYOK） | `MODEL_CONFIG_REQUIRED` | 400 | 否 |
| 模型额度不足 | `MODEL_QUOTA_EXCEEDED` | 402 | 否 |
| 密钥/配置无效 | `MODEL_CONFIG_INVALID` | 400 | 否 |
| 文件无法解析 | `FILE_PARSE_FAILED` | 422 | 通常否 |
| 其他未预期 | `INTERNAL_ERROR` | 500 | 视情况 |

- 对外错误体遵循 `api.md 一.2`（扁平 + `retryable` + 可选 `details.reason`）。

## 十一、验收标准

- 解析：pdf/docx/txt 正常解析；空文件/不支持类型/损坏/加密/无文本层返回对应 `reason`。
- 索引：删除材料后 RAG 不再命中其分块。
- 检索：跨用户不可检索到他人分块（权限断言）。
- 生成：准备稿/纪要/行动项/问题均以草稿/候选落库，未确认不进入任务。
- 稳定性：模型超时/限流有重试；失败返回统一错误码且前端可提示重试。
- 可追溯：问答 `sources`、行动项 `source`、纪要 `source_record_ids` 均可回溯来源。

## 十二、关联文档

- 接口：`api.md 五`（AI 应用）。
- 表结构：`database.md 三`。
- AI 层入口说明：`module-development-spec.md` 的 M03/M04/M05/M06/M07/M09。
- 环境变量：`development.md`、`docker/.env.example`（`LLM_*`/`EMBEDDING_*`）。
