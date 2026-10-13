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
5. **密钥服务端化**：LLM/Embedding 密钥仅来自环境变量，绝不下发前端。

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

- 配置来源：`settings.llm_api_base`、`settings.llm_api_key`、`settings.llm_model`（`config.py`）。
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

## 四、Embedding 与文本切分（`ai/embeddings/`）

### 4.1 Embedding 客户端

```python
class EmbeddingClient:
    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]: ...
```

- 模型：`settings.embedding_model`（阿里百炼 `text-embedding-v3`）；维度：`settings.embedding_dim = 1024`。
- 批量：每批 ≤ 16 条；单批超时 30s；失败重试 2 次（退避 1s/3s）。
- 维度校验：返回向量长度必须等于 `settings.embedding_dim`，否则报 `INTERNAL_ERROR` 并记录。

### 4.2 切分策略

- 按字符近似切分：`chunk_size = 800`，`overlap = 120`（避免语义被截断）。
- 优先在段落/换行处切分，尽量不切断句子。
- 每块写入 `document_chunks(material_id, content, chunk_index)`，`chunk_index` 从 0 连续。
- 重解析时**先删除该材料旧分块再写入**（避免新旧混合检索）。

## 五、RAG 检索（`ai/rag/`）

### 5.1 数据与权限

- 载体：`document_chunks.embedding vector(1024)`（`database.md 三.10`）。
- **权限范围**：检索必须经 `document_chunks → meeting_materials → meetings` 关联，限定 `meetings.user_id = current_user.user_id`；禁止先全库检索再过滤。
- 只检索 `embedding IS NOT NULL` 的分块。

### 5.2 检索接口

```python
class RetrievedChunk:
    chunk_id: str
    material_id: str
    meeting_id: str
    excerpt: str
    score: float

class Retriever:
    def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        scope: str = "current_meeting",   # current_meeting | current_and_history
        current_meeting_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]: ...
```

- `scope=current_meeting`：仅当前会议材料；`current_and_history`：该用户全部会议材料。
- 排序：`ORDER BY embedding <=> :query_vector`（余弦距离），取前 `top_k`；低于 `min_score` 丢弃。
- 无结果或全部低于阈值 → 返回空列表，由上层置 `insufficient_evidence=true`。

### 5.3 来源返回

- `api.md 五.6` 的 `sources[]` 由检索结果映射：`{ meeting_id, material_id, record_id(null), excerpt }`。
- 不得伪造引用；`excerpt` 取自命中分块原文。

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
  → 建材料记录 processing_status=uploaded
  → 解析(ai/parsers)：processing_status=processing
      ├─ 成功：写 content，processing_status=processed
      │        切分 + Embedding → document_chunks
      └─ 失败：processing_status=failed，写 parse_error（安全摘要）
```

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
- **删除材料**：同步删除文件对象与 `document_chunks`；`meeting_records.source_material_id` 置空（`database.md 七`）。

## 七、Prompt 管理（`ai/prompts/`）

- 所有模板集中在 `ai/prompts/`，按功能命名（如 `prepare.py`、`minutes.py`、`extract_action_items.py`、`chat.py`）。
- 模板函数签名：`build_xxx(context: dict) -> list[dict]`，注入会议主题、材料片段、记录等上下文。
- 不把用户原文或密钥写入日志。

## 八、AI 功能规格

> 接口契约见 `api.md 五`；以下为实现要点。

### 8.1 会前准备 `POST /meetings/{id}/prepare`
- 输入：会议信息 + 材料分块（当前会议）。
- 输出（结构化）：`{ summary: str, checklist: list[str] }`。
- 落库：**每次生成新增一条** `preparations`（`status=draft`，`version=1`）。
- 失败：置 `failed` 并返回统一错误。

### 8.2 会中问答 `POST /meetings/{id}/chat`
- 流程：检索（`scope`）→ 组装 Prompt → LLM 生成 → 返回 `{answer, sources[], insufficient_evidence}`。
- 检索为空 → `insufficient_evidence=true` 且回答明确说明无法确认。
- 不落库（问答历史非 MVP）。

### 8.3 整理记录 `POST /meetings/{id}/organize`
- 输入：显式 `record_ids`。输出 `{ organized_content, source_record_ids[] }`。不落库。

### 8.4 纪要生成 `POST /meetings/{id}/minutes/generate`
- 输入：`record_ids`（+ `include_action_items`）。
- 输出：`minutes.content`。每次生成**新增一条** `meeting_minutes`（`status=draft`，`version=1`），记录 `source_record_ids`。
- 编辑（`PATCH`）原地更新并 `version` 递增；确认置 `confirmed`。

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
