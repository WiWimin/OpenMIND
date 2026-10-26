# OpenMIND「用户自带大模型 BYOK」架构专项源码审计报告

> 生成时间：2026-10-17
> 审计范围：LLM BYOK + Embedding BYOK 的源码实现、供应商兼容性、密钥安全、用户隔离与真实调用验证。
> 审计性质：只读审计 + 隔离账号验证，未修改任何代码。

## 一、审计结论（一句话）

**BYOK 的机制已完整实现且隔离/加密/脱敏正确，用户能够独立配置自己的 LLM 与 Embedding Key；但当前实现存在「服务端全局回退」，未配置用户会静默消费团队额度，因此尚未完全满足「团队不承担用户 Token 费用」的产品要求；Embedding 真实调用因免费额度耗尽而 BLOCKED，无法端到端确认「完全不依赖团队额度的 RAG 闭环」。**

---

## 二、LLM BYOK 实现状态：✅ 已实现

| 层 | 位置 | 状态 |
| --- | --- | --- |
| 前端设置页 | `frontend/src/views/settings/ModelSettingsView.vue` | ✅ 独立「大模型(LLM)」卡片，可填 API 地址 / API 密钥(password) / 模型名 |
| 前端 API | `frontend/src/api/settings.ts`（GET/PUT/DELETE `/me/settings/model`） | ✅ |
| 前端状态 | `frontend/src/stores/modelConfig.ts`、`types/modelConfig.ts` | ✅ |
| 配置 API | `backend/app/api/v1/settings.py` | ✅ 三个端点，均按 `current_user.user_id` 隔离 |
| 数据表 | `backend/app/models/model_config.py`（`user_model_configs`，`user_id` 主键） | ✅ |
| 密钥加密 | `backend/app/core/crypto.py`（Fernet，密钥由 `SECRET_KEY` sha256 派生） | ✅ |
| 配置解析 | `backend/app/services/model_config_service.py` → `resolve_model_config` | ✅ 用户配置优先 |
| 客户端构建 | `build_llm_client` → `LLMClient(api_base, api_key, model)` | ✅ |

**关键调用链（真实请求追踪）**：

```
HTTP PUT /me/settings/model
  → settings.py:put_model_config(current_user.user_id)
  → model_config_service.save_model_config（probe 校验 → encrypt → upsert）

业务调用（例：会前准备）
  → preparation_service.generate_preparation(db, meeting_id, user_id)
  → resolve_model_config(db, user_id)   # 读 user_model_configs，解密
  → build_llm_client(config)            # 用解析出的 user key/base/model 构造
  → PreparationService(client).generate(...)
```

代码证据（`grep` 全仓）：所有业务代码的 `LLMClient(`/`EmbeddingClient(` 构造仅出现在 `model_config_service.py`（build/probe），业务层无任何无参构造（即不存在直接吃全局配置的调用点）。调用点清单见第八节。

---

## 三、Embedding BYOK 实现状态：✅ 已实现（真实调用 BLOCKED）

| 审计项 | 结论 | 证据 |
| --- | --- | --- |
| 独立 Provider/Key/Base/Model/维度 | ✅ 独立字段 | `user_model_configs` 有 `embedding_api_base/key_enc/model/dim`，与 LLM 字段并列 |
| 上传资料向量化用用户配置 | ✅ | `indexing_service.index_material` → `resolve_model_config(db, material.user_id)` → `build_embedding_client` |
| RAG 查询向量用用户配置 | ✅ | `rag/retriever.py` `VectorRetriever.__init__` → `resolve_model_config(db, user_id)`；`embed_query` 用 `build_embedding_client(config)` |
| 是否意外调用团队统一 Embedding Key | ⚠️ 存在回退 | 仅当用户未配置时 `resolve` 回退 `settings.embedding_*`（见第六节） |
| 换模型后维度兼容 | ✅ 强制锁定 | `EMBEDDING_DIM=1024`；保存时 `_probe_embedding_dim` 实测维度，非 1024 直接拒绝（`MODEL_CONFIG_INVALID`），不会出现历史向量维度漂移 |
| 不同用户索引隔离 | ✅ | 检索按 `document_chunks → meeting_materials → meetings` 用 `meetings.user_id` 过滤（`rag/retriever.py`），各用户只检索自己分块 |

> 维度策略说明：系统**不允许**用户配置非 1024 维 Embedding（保存即拒绝），因此不存在「历史向量维度不兼容」需要迁移的场景——这是当前实现下最稳妥的兼容性处理（代价：不兼容 768/3072 维等非 1024 模型）。

---

## 四、供应商兼容性（区分：已实现 / 已验证 / 仅声明）

| 供应商/协议 | 状态 | 依据 |
| --- | --- | --- |
| OpenAI 兼容协议（通用） | **已实现** | `LLMClient` POST `{base}/chat/completions`；`EmbeddingClient` POST `{base}/embeddings`，均 `Authorization: Bearer` + `response_format=json_object`（可选） |
| DeepSeek（`https://api.deepseek.com`） | **已验证** | 实测 `deepseek-flash` 调用成功（637ms 返回「正常」） |
| 阿里百炼 DashScope 兼容模式（`text-embedding-v3`） | **已实现未通过验证** | 协议为 OpenAI 兼容 `/embeddings`；但免费额度耗尽，本次未实测成功 |
| 其他（OpenAI/Moonshot/Kimi 等） | **仅声明兼容** | 代码层是协议级兼容，但无对应真实 Key，**未验证** |

> 说明：系统**没有**专用供应商 SDK 或供应商预设下拉框；「供应商」由用户填写的 `api_base` URL 表达。因此「支持某供应商」的严格含义是「支持该供应商的 OpenAI 兼容端点」，任何声称支持特定厂商的说法都必须经真实 Key 验证，本次仅 DeepSeek 通过验证。

---

## 五、密钥安全与用户隔离：✅ 通过

| 检查项 | 结论 | 证据 |
| --- | --- | --- |
| 密钥保存（加密落库） | ✅ | 实测 `user_model_configs.llm_api_key_enc` 为 Fernet 密文（`gAAAAA...`，140 字符），库内无 `sk-` 明文 |
| 密钥读取返回脱敏 | ✅ | `GET` 返回 `llm_api_key_masked = sk-...d92a`，响应体中无明文 key |
| 日志处理 | ✅ | 全仓 grep 无任何 `logger.*api_key` 打印；客户端日志仅记 `model/latency/usage/count/dim` |
| 错误消息 | ✅ | probe/客户端错误均为通用文案，不含 key |
| 用户隔离（A 不能读/覆盖 B） | ✅ | 每行以 `user_id`（JWT sub）为主键；实测：B 读取 `llm_source=global`（非 A 的 `user`），B 写自己的配置后 A 的 `llm_source` 仍为 `user` |
| 保存时 probe 校验 | ✅ | 无效 key → 400 `MODEL_CONFIG_INVALID` |

---

## 六、关键缺陷：全局回退导致「团队仍在付费」

**问题**：`resolve_model_config` 的优先级是「用户配置 > 服务端全局」，而非「仅用户配置」：

```python
llm_api_key = _decrypt_or_empty(row.llm_api_key_enc if row else None) or settings.llm_api_key
```

**实测证据**：未配置任何 Key 的用户 B 调用「会前准备」→ **HTTP 200**，因为它静默回退到了团队在 `docker/.env` 里配的 DeepSeek Key（团队付费）。`GET /me/settings/model` 对 B 返回 `llm_source=global`。

**异常处理也不够友好**（均映射为 500 `INTERNAL_ERROR`，而非清晰 4xx）：

| 场景 | 当前行为 | 期望 |
| --- | --- | --- |
| 未配置 Key（且全局空） | `500 INTERNAL_ERROR "模型服务未配置"` | `400/402 MODEL_CONFIG_REQUIRED` |
| 运行期 key 失效（provider 401） | `500 INTERNAL_ERROR "模型服务调用失败"` | `MODEL_CONFIG_INVALID` |
| 运行期余额不足（provider 400/402） | `500 INTERNAL_ERROR`（429 才映射 RATE_LIMITED） | `MODEL_QUOTA_EXCEEDED` |
| 模型不可用 | `500 INTERNAL_ERROR` | `MODEL_CONFIG_INVALID` |

> 保存时 probe 能拦截「初始无效/配额不足」，但运行期（key 被吊销、额度中途耗尽）会以 500 暴露给用户。

---

## 七、真实验证结果汇总

| 验证项 | 结果 | 说明 |
| --- | --- | --- |
| 用户自配 LLM Key 后成功调用 | **PASS** | 用团队已授权的 DeepSeek Key 作为用户 A 的自配 LLM，会前准备 HTTP 200 |
| 用户自配 Embedding Key 后生成向量 | **BLOCKED** | 无有效 Embedding Key（百炼免费额度耗尽） |
| 上传资料→索引→语义检索→带来源问答 | **BLOCKED** | 依赖 Embedding，无有效 Key |
| 修改 A 配置不影响 B | **PASS** | `llm_source` 区分（user/global），B 写不覆盖 A |
| 无效 Key 被正确拒绝 | **PASS** | 400 `MODEL_CONFIG_INVALID` |
| 密钥不通过 API/错误/日志泄漏 | **PASS** | 脱敏返回、无日志、密文落库 |

> 「独立用户 key 与团队全局 key 严格区分」的运行时证明为 **BLOCKED**：仅有团队一把有效 LLM Key，无法用第二把不同 Key 证明「用户 key 被真正使用而非全局」。但代码追踪（`resolve→build`，无任何业务无参构造）已从机制上证明该路径正确。

---

## 八、关键代码文件清单

| 文件 | 作用 |
| --- | --- |
| `backend/app/services/model_config_service.py` | `resolve_model_config`/`build_*_client`/`save`/`get_read`/probe |
| `backend/app/core/crypto.py` | Fernet 加解密（密钥由 SECRET_KEY 派生） |
| `backend/app/models/model_config.py` | `user_model_configs` 表 |
| `backend/app/repositories/model_config_repository.py` | 按 user_id 的 upsert/delete |
| `backend/app/api/v1/settings.py` | GET/PUT/DELETE `/me/settings/model` |
| `backend/app/schemas/model_config.py` | 写/读 schema（读含 masked + source） |
| `backend/app/ai/llm/client.py` | `LLMClient`（`/chat/completions`，Bearer，无 key 日志） |
| `backend/app/ai/embeddings/client.py` | `EmbeddingClient`（`/embeddings`，维度校验，无 key 日志） |
| 调用点（业务层注入用户配置） | `preparation_service` / `minutes_service` / `action_item_service` / `issue_service` / `ai_chat_service` / `indexing_service` / `ai/rag/retriever.py` |
| 前端 | `views/settings/ModelSettingsView.vue`、`api/settings.ts`、`stores/modelConfig.ts`、`types/modelConfig.ts` |

---

## 九、是否满足产品要求与最小修改方案

### 是否满足「团队不承担用户 Token 费用」？

**未完全满足。** 机制已就绪，但两处缺口：

1. **全局回退**：未配置用户会静默使用团队 `docker/.env` 的全局 Key（团队付费）。要满足要求，必须让「用户自备」成为唯一来源，或显式关闭回退。
2. **运行期错误映射为 500**：未配置/失效/额度不足场景的用户体验与可诊断性差。

### 最小必要修改方案（按优先级）

| # | 修改 | 位置 | 影响 |
| --- | --- | --- | --- |
| 1 | 关闭/可开关全局回退：`resolve_model_config` 在无用户配置时返回空，不再回退 `settings.llm_*`/`embedding_*`（或加 `ALLOW_GLOBAL_FALLBACK` 开关，默认 false） | `model_config_service.py` | 让「团队零费用」成立；未配置用户触发明确错误 |
| 2 | 未配置 Key 时返回清晰错误码 `MODEL_CONFIG_REQUIRED`（400/402），而非 500 | `model_config_service` + 客户端 `_ensure_configured` | 用户体验 |
| 3 | 运行期 provider 401/402/400 映射为 `MODEL_CONFIG_INVALID` / `MODEL_QUOTA_EXCEEDED`，而非 `INTERNAL_ERROR` | `llm/client.py`、`embeddings/client.py` `_http_error` | 可诊断性 |
| 4 | （可选）前端对 `source=none` 增加引导「请自备 Key」 | `ModelSettingsView.vue` | 引导用户配置 |

> 以上为最小必要改动，均不涉及数据迁移；`user_model_configs` 表结构与加密方案无需变更。

---

## 十、最终结论

**用户能够独立配置自己的 LLM 与 Embedding Key（前端可填、后端按用户隔离加密存储、调用链全程使用用户配置、密钥脱敏不泄漏、无效 Key 被拒）。**

**但在当前实现下，尚不能确认「不依赖团队统一模型额度完成完整 RAG 业务闭环」**，原因是：

1. Embedding 真实调用因阿里百炼免费额度耗尽而 **BLOCKED**（无法验证「上传→索引→语义检索→带来源问答」）。
2. 存在「用户 > 全局」回退，未配置用户仍会消费团队额度——**除非关闭全局回退**，否则「团队零费用」不成立。

**要达到发布级 BYOK 验收，需要**：① 解除 Embedding 额度（或提供一把有效 1024 维 Embedding Key）以补测 RAG 闭环；② 实施第九节第 1 项（关闭全局回退）+ 第 2/3 项（错误映射）。

---

## 十一、修复记录（2026-10-17 已实施）

### 修复文件与变更

| 文件 | 变更 |
| --- | --- |
| `backend/app/core/config.py` | 新增 `allow_global_fallback: bool = False`（默认关闭） |
| `backend/app/services/model_config_service.py` | `resolve_model_config` 改为仅解析用户配置，仅在 `allow_global_fallback=True` 时回退全局 |
| `backend/app/ai/llm/client.py` | `__init__` 用 `is None` 区分「未传」与「显式空」（杜绝空值回退全局）；`_ensure_configured` 抛 `MODEL_CONFIG_REQUIRED`；`_http_error` 401/403→`MODEL_CONFIG_INVALID`、402/配额→`MODEL_QUOTA_EXCEEDED`、429→`RATE_LIMITED`、5xx→`INTERNAL_ERROR`、其余 400→`MODEL_CONFIG_INVALID`（按响应体含 quota 字样识别额度不足） |
| `backend/app/ai/embeddings/client.py` | 同 LLM 客户端：`is None` 区分、`MODEL_CONFIG_REQUIRED`、错误映射规范化 |
| `docker/.env.example` | 文档化 `ALLOW_GLOBAL_FALLBACK=false`（BYOK 说明） |
| `docs/api.md` | 错误码表新增 `MODEL_CONFIG_REQUIRED`(400)、`MODEL_QUOTA_EXCEEDED`(402) |
| `frontend/src/utils/errors.ts` | 新增 `MODEL_CONFIG_REQUIRED`、`MODEL_QUOTA_EXCEEDED` 友好提示 |

### 测试变更与结果

| 项 | 结果 |
| --- | --- |
| 后端 `ruff check .` | PASS |
| 后端 `pytest` | **PASS（205 项）** |
| 前端 `typecheck` / `lint` / `build` | PASS |
| 前端 `test` | PASS（309 项；`router.spec.ts` 有 1 例 5000ms 超时抖动，重跑 9/9 通过，与本次无关） |

新增/修改的测试覆盖：
- 未配置用户 resolve 返回空（即使 `.env` 有全局 Key 也不回退）
- `allow_global_fallback=True` 时才回退全局
- 未配置 → 客户端 `chat/embed` 抛 `MODEL_CONFIG_REQUIRED`（在使用前、网络调用前）
- 空配置不落到全局（`client.api_base == ""`）
- 401/403 → `MODEL_CONFIG_INVALID`；402 → `MODEL_QUOTA_EXCEEDED`；400 带 quota 响应体 → `MODEL_QUOTA_EXCEEDED`；400 普通 → `MODEL_CONFIG_INVALID`；429 → `RATE_LIMITED`（LLM 与 Embedding 两条路径均覆盖）
- 用户 A/B 配置隔离、脱敏、密文落库

### 运行时验证（真实环境）

| 场景 | 结果 |
| --- | --- |
| `allow_global_fallback` 默认值 | `False`（未设置任何环境变量） |
| 未配置用户调用「会前准备」 | **HTTP 400 `MODEL_CONFIG_REQUIRED`**（不再 200 静默消耗团队额度） |
| 未配置用户 `GET /me/settings/model` | `llm_source=none`、`masked=''` |
| 团队连通性脚本 `check_ai.py`（无参客户端显式读全局） | 仍可用（`[OK] deepseek-flash 797ms`），不受影响 |

### 遗留问题

1. Embedding 真实调用仍 **BLOCKED**（阿里百炼免费额度耗尽），RAG「上传→索引→带来源问答」端到端尚未用真实 Key 验证。
2. 前端 `router.spec.ts` 存在偶发超时（非本次引入，建议后续单列排查）。
3. 前端「模型设置」已有 `source=none` 展示与保存提示，但未在 AI 功能入口做「未配置跳转设置页」的强引导（可选增强，非阻断）。

### 结论（修复后）

**未配置用户 Key 时，系统不再消耗团队模型额度。** 代码路径证明：`resolve_model_config` 仅解析用户配置（无 `ALLOW_GLOBAL_FALLBACK` 时不回退），业务调用链全部经 `resolve → build_*`，未配置时客户端在 `_ensure_configured`（网络调用之前）抛出 `MODEL_CONFIG_REQUIRED`；实测未配置用户调用返回 400 而非 200。团队全局 Key 仅用于 `check_ai.py` 等显式无参构造的运维脚本，不用于任何用户请求。

---

## 十二、最终验收结论（2026-10-17，最终答复）

### 逐项结论

| 问题 | 结论 |
| --- | --- |
| BYOK 机制是否通过 | **通过**（代码路径 + 205→207 自动化测试 + 运行时验证均证明：用户配置优先、无全局回退、隔离/加密/脱敏正确） |
| 未配置用户 Key 时是否会产生团队模型调用费用 | **不会**。未配置用户调用 AI 返回 400 MODEL_CONFIG_REQUIRED，发生在任何网络请求之前；代码全链无无参客户端或 settings.llm_*/embedding_* 直读（仅运维脚本 check_ai.py/check_rag.py 显式无参构造，不进入用户请求） |
| 用户自带 LLM 是否真实调用成功 | **机制验证通过**（隔离账号自配 LLM → 会前准备 HTTP 200，真实返回 summary + 5 项 checklist）；但「独立于团队 Key 的用户自有 Key」未验证（当前仅有一把有效 deepseek Key，作为用户配置值测试）→ 该项严格标记 **BLOCKED（缺第二把独立 Key）** |
| 用户自带 Embedding 是否真实调用成功 | **BLOCKED**（阿里百炼免费额度耗尽，check_ai.py 现返回 MODEL_QUOTA_EXCEEDED；无可用 1024 维 Embedding Key） |
| 完整 RAG 是否通过 | **BLOCKED**（依赖 Embedding，无法验证「上传→索引→语义检索→带来源回答」） |

### 所需配置（解除 BLOCKED 的条件）

- Embedding：提供一把有额度、返回 **1024 维** 向量的 OpenAI 兼容 Embedding Key（例如百炼充值后、或任何支持 1024 维的 embedding 端点）。
- 独立 LLM Key（若需证明「独立于团队」）：一把与团队全局 Key 不同的有效 LLM Key。

### 发布阻塞项（剩余）

1. **RAG 真实链路未验证**（Embedding 额度耗尽）——发布前需一把有效 1024 维 Embedding Key 补测。
2. **BYOK 的「独立用户 Key」未验证**——需第二把独立 LLM Key 以证明与团队额度彻底解耦（当前只能证明「机制正确 + 未配置不落全局」）。
3. **前端 outer.spec.ts 偶发超时**（非本次引入，建议单列排查）。
4. **develop → main 未发布**，且本次修复**未提交/未推送/未合并/未部署**（按交付要求保留为工作区改动，待团队 review）。
