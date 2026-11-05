# 02 文档与代码差异（document-diff）

> 对比：4.1（基线 7454a20，2026-10-31）↔ 5.0（基线 ff42641，2026-11-01）。结论：多数新增已在设计文档中同步（`ai-design.md`、`database.md`、`api.md`、`design-baseline.md`），少数文档仍有陈旧表述，需在 5.0 正文中按代码更正，**不修改设计文档原文**。

## 一、统计口径差异

| 项 | 4.1 | 5.0（当前） | 变化 |
| --- | --- | --- | --- |
| API Router 模块 | 16 | 16 | 不变 |
| HTTP 路由（含 `/health`） | 69（68+1） | 77（76+1） | +8（新增音频分片/分段、设置模型清单、模板等） |
| 方法分布 | G24/P24/Pa8/Pu3/D9 | G25/P30/Pa9/Pu3/D9 | +1 GET、+6 POST、+1 PATCH |
| ORM 表 | 16 | 16 | 不变（新增/删除字段，未增删表） |
| 数据库迁移 | 19（head 0019） | 22（head 0022） | +3（0020/0021/0022） |
| 后端测试 | 304 passed | 350 passed | +46 |
| 前端测试 | 403（401+2） | 449（447+2） | +46 |
| E2E spec / case | 5 / 7 | 5 / 7 | 不变，均未执行 |

## 二、内容差异（相对 4.1，需要更新/新增/删除）

### 1. 需更新（4.1 表述已不准确）

| 主题 | 4.1 表述 | 5.0 事实（代码） |
| --- | --- | --- |
| Embedding 配置 | LLM 与 Embedding 均为用户自备（BYOK） | **Embedding 仅服务端统一配置**（`docker/.env` 的 `EMBEDDING_*`），用户不可自备；`0020` 删除用户 embedding 字段 |
| 用途级模型 | 四用途独立模型 | **仅覆盖模型名**，api_base/api_key 不变 |
| 请求级覆盖 | 仅限已登记模型（`MODEL_NOT_ALLOWED`） | 直接覆盖模型名，有效性交由服务商判定；另有 `GET /models` 拉取服务商模型清单 |
| 音频能力 | 批量上传转写，非实时；实时未实现 | **分片边录边转已实现**（start/chunk/finish + 分段重试/标记/编辑/确认），仍**非流式**（WebSocket/SSE 未实现） |
| 保存校验 | 保存时探测 | LLM `probe()`；遇 429 视为密钥有效放行，返回 `llm_probe_verified=false` |
| 整理能力 | 单一整理（organize） | **多任务整理链**：organize / summary / brief / polish；summary/polish 输出结构化 JSON |
| 会议模板 | 内置 5 + 自定义（文件） | 增加 `category`；支持"仅文本"自定义模板（file_name/storage_key 可空） |

### 2. 需新增（4.1 未覆盖）

- 音频实时分片转写体系（12 个音频端点、`segments` JSONB、标记类型、分片重试、合并/清理）——作为 5.0 独立重点章节。
- 多任务整理链与结构化摘要/口误校正（`ai/prompts/organize.py`、`_parse_structured`）。
- 服务商模型清单（`GET /models`）与模型选择器（`ModelPickerPopover`）。
- 输入源三级回退（text > audio_id > record_ids > 最近记录）。
- 模板分类与内置/自定义的统一选择器（`TemplatePickerPopover`）。

### 3. 需保留（4.1 准确且仍成立）

- 16 ORM 表、用户数据隔离、越权 404。
- RAG：SQL 层权限下推 + 应用层余弦（非 ANN）、`top_k=5`/`min_score=0.3`、chunk 800/overlap 120、会议记录不入索引、记忆按用途注入、证据不足处理。
- 状态机：材料/纪要/准备稿/行动项/任务/问题/会议归档；转任务幂等（`action_id` 唯一）。
- 安全：JWT HS256、bcrypt、Fernet 加密 + 轮换（`SECRET_KEY_PREVIOUS`）、SSRF 校验、`ALLOW_GLOBAL_FALLBACK=false`。
- 部署：开发 Compose（db/backend/frontend/asr profile，127.0.0.1），单 worker、前端 dev server；生产项未实现。

### 4. 需删除/纠正

- 删除"Embedding 用户自带密钥"相关描述。
- 纠正"实时流式 ASR 未接入"为"分片边录边转已实现，流式（WebSocket/SSE）未实现"。
- 不宣称 RAG 准确率/召回率/性能已达某水平（无评测）。

## 三、项目内设计文档一致性检查（对应任务书第八节）

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `README.md` | 轻微陈旧 | 功能已列音频与 BYOK；但第 288 行"实时流式 ASR 未接入"未区分"分片边录边转已实现"，需在 5.0 正文澄清（不改 README） |
| `AGENTS.md` | 基本一致 | 第 9 行"音频转写（需配置 ASR 服务）"较泛，可接受 |
| `docs/architecture.md` | **陈旧** | 第 15、31 行仍标 AI 能力层"（后续阶段）"，与已实现事实不符；5.0 正文按实现重绘架构，不改原文 |
| `docs/requirements.md` | 轻微陈旧 | M06"音频转写（扩展）"未覆盖实时分片转写范围 |
| `docs/design-baseline.md` | **一致** | D-20/D-21/D-22/D-27 已准确记录"Embedding 服务端 + LLM probe"等决策 |
| `docs/api.md` | 一致 | 已包含 audio live/segments 等端点 |
| `docs/database.md` | 一致 | 已包含 0020 删字段、`meeting_audio.segments` |
| `docs/ai-design.md` | 一致 | 已写明"LLM 用户自备、Embedding 服务端统一" |
| `docs/testing.md` | 一致 | 仅描述命令与策略，无硬编码过期计数 |

> 结论：`ai-design.md`、`database.md`、`api.md`、`design-baseline.md` 已随代码更新；`architecture.md`、`requirements.md`、`README.md` 存在陈旧/含糊表述，5.0 正文以代码为准纠正，**不擅自修改这些设计文档或业务代码**。

## 四、5.0 正文取舍原则

1. 保留 4.1 中经代码复核仍准确的架构、RAG、状态机、安全分析。
2. 更新 BYOK（Embedding 收归服务端）、音频（分片边录边转）、整理链、模板、模型清单。
3. 新增"音频处理与实时转写体系"独立章节（任务书要求）。
4. 所有统计以 ff42641 重算，不沿用 4.1 的 16/69/19/304/403。
