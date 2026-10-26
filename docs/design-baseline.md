# OpenMIND 设计基线（权威索引与决策日志）

> **文档目的**：定义各设计文档的职责与**唯一事实来源**，集中记录已定决策，避免同一规则在多份文档中重复声明后分叉。
>
> **使用方式**：开发、联调、测试前先读本文件；任何契约变更**先改被引用文档，再回填本文件的决策日志**。

## 一、文档职责与唯一事实来源

| 文档 | 唯一负责（事实来源） | 不负责（只引用） |
| --- | --- | --- |
| `design-baseline.md`（本文件） | 文档职责、决策日志、变更流程 | 具体字段/接口定义 |
| `requirements.md` | 产品定位、MVP 范围、功能需求、验收标准 | 接口字段、表结构 |
| `architecture.md` | 分层与边界、技术栈、数据流、部署 | 接口字段、表结构 |
| `database.md` | **表、字段、类型、约束、状态枚举、索引、删除策略** | 接口请求/响应 |
| `api.md` | **接口路径、请求/响应、错误码、鉴权、分页、PATCH 语义** | 表结构（引用 `database.md`） |
| `ai-design.md` | AI 调用、文件解析、RAG、超时重试、幂等、失败补偿 | 业务 CRUD 接口（引用 `api.md`） |
| `module-development-spec.md` | 模块实现细则、`Mxx-NN` 任务拆分与验收 | 与 `api.md`/`database.md` 冲突的字段定义 |
| `module-task-plan.md` | 阶段交付与里程碑 | 字段/接口细节 |
| `testing.md` | 测试分层、命令、覆盖口径 | 接口字段 |
| `development.md` | 环境要求、启动、常用命令、故障排查 | 接口字段 |
| `collaboration-rules.md` | **三流分工、分支模型、合并/同步/发布流程** | 接口字段、表结构 |
| `CONTRIBUTING.md` | 提交信息、PR 模板与流程摘要（分支流程引用 `collaboration-rules.md`） | 设计细节 |

**权威关系**：

```text
design-baseline.md ──索引──► requirements / architecture / database / api / ai-design
                                                   │            │
                                          module-development-spec / testing / development
                                        （实现与验证所依据的契约 = database + api + ai-design）
```

- `database.md`、`api.md`、`ai-design.md` 三者是实现的**直接依据**，其余文档只引用，不重述其字段与接口。
- 若任一文档与 `database.md`/`api.md`/`ai-design.md` 冲突，**以这三者为准**并同步修正。

## 二、变更流程（契约变更必须遵循）

1. 字段/表变更 → 先改 `database.md`；接口变更 → 先改 `api.md`；AI 链路变更 → 先改 `ai-design.md`。
2. 在 §三 决策日志补记或更新对应条目。
3. 同步受影响文档（`module-development-spec` / `testing` / `architecture` / `requirements`）。
4. PR 描述中说明：改动范围、是否影响数据库（须附 Alembic 迁移）、是否影响其他成员、是否需冻结接口。

## 三、已定决策日志

| 编号 | 决策 | 结论 | 落地位置 |
| --- | --- | --- | --- |
| D-01 | 登录标识 | 唯一 `name` + `password`（无 email） | `database.md 三.1`、`api.md 一/二` |
| D-02 | 鉴权方式 | `Authorization: Bearer <token>`；令牌为 **HS256 JWT**；MVP 不提供 refresh | `api.md 一/二`、`architecture.md` |
| D-03 | 密码哈希 | `passlib[bcrypt]` | `database.md 三.1`、`requirements.txt` |
| D-04 | 主键格式 | 带前缀字符串 `VARCHAR(40)`（`usr_`/`mtg_`/…） | `database.md 二` |
| D-05 | Embedding | 阿里百炼 `text-embedding-v3`，维度 **1024**，`vector(1024)` | `database.md 三.10`、`ai-design.md` |
| D-06 | 会议状态 | MVP 仅 `scheduled` / `archived` | `database.md 五`、`api.md 三` |
| D-07 | 成功信封 | 强制 `{ "status": "success", "data": ... }` | `api.md 一.1` |
| D-08 | 错误信封 | `{ "status":"error", "error_code", "message", "retryable", "details"? }`（扁平平铺，`details` 可选） | `api.md 一.2/1.3`、`exceptions.py` |
| D-09 | 越权 | 统一 `404 RESOURCE_NOT_FOUND` | `api.md 一.6` |
| D-10 | 分页 | `page`/`page_size`/`total`/`total_pages` + `data.items`/`data.pagination` | `api.md 一.4` |
| D-11 | 时间 | 库内 `TIMESTAMPTZ` 存 UTC；接口返回带时区 ISO 8601 | `api.md 一.7`、`database.md 二.2` |
| D-12 | M09 定义 | M09 = **未解决问题管理**；异常处理、联调、部署归 **M10** | `requirements.md`、`module-task-plan.md` |
| D-13 | 会议删除 | 存在已转换行动项或个人任务引用时**禁止删除，返回 409**；`action_items.meeting_id` 保持非空 | `database.md 七`、`api.md 三.5` |
| D-14 | 版本策略 | 每次**生成**新增记录（1:N）；对同一条记录的**编辑**原地更新并 `version` 递增；不保留编辑中间态历史 | `database.md 三.5/3.6`、`ai-design.md 八.1/8.4`、`api.md 五` |
| D-15 | 提取幂等 | 重复 extract 不去重（可能产生重复候选）；转任务以 `action_id` 唯一保证幂等 | `api.md 五.15/5.16`、`database.md 三.8` |
| D-16 | 上传限制 | 允许扩展名 `pdf/docx/txt`；单文件 ≤ `MAX_UPLOAD_MB`（默认 20MB）；MIME 嗅探为后续 | `api.md 四`、`database.md 三.3` |
| D-17 | 会议列表筛选 | MVP 支持 `page`/`page_size`/`status`；`keyword`/`start_time`/`end_time` 为后续增强 | `api.md 三.1` |
| D-18 | 错误详情 | 可选 `details` 用于字段校验错误与 `FILE_PARSE_FAILED.reason` | `api.md 一.2/1.3` |
| D-19 | 登录落点与外壳 | 认证后默认落点 `/meetings`；全局外壳（顶栏/导航）归 M02；根路径按登录态重定向到登录页或 `/meetings` | `module-development-spec.md M02`、`frontend/src/router` |
| D-20 | 模型密钥来源 | 用户可在 `/me/settings/model` 自备 LLM/Embedding 配置（Fernet 加密存库、明文不回显），或走服务端 `docker/.env` 全局；优先级用户 > 全局；Embedding 维度固定 1024 | `api.md 二.5`、`ai-design.md 三.5`、`database.md 三.10` |
| D-21 | 模型配置安全 | 非开发环境拒绝弱 `SECRET_KEY`；轮换使用 `SECRET_KEY_PREVIOUS`；`api_base` 默认仅允许 HTTPS 公网地址；全局密钥不返回脱敏片段 | `api.md 二.5`、`ai-design.md 三.5`、`docker/.env.example` |
| D-22 | BYOK 默认不回退全局 | `ALLOW_GLOBAL_FALLBACK=false` 为默认值；未配置用户返回 `MODEL_CONFIG_REQUIRED`，避免团队承担用户 Token 费用 | `api.md 二.5`、`ai-design.md 三.5`、`config.py` |
| D-23 | 记录检索先受限 | 当前阶段只把当前会议最近记录作为问答受限上下文；完整历史记录检索需独立 schema/检索设计，不宣称已实现 | `api.md 五.7`、`ai-design.md 五/八.2` |

## 四、待确认事项

| 项 | 说明 |
| --- | --- |
| `[提案]` 接口采纳 | `api.md` 中材料列表、纪要读取/编辑/确认、记录删除、行动项详情/删除，需团队确认后转正式 |
| MIME 嗅探 / 音频转写 | 均超出当前 MVP |
| 向量索引类型（HNSW/IVFFlat） | 待数据量确定后选择（`database.md 六`） |
| 并发编辑冲突 | MVP 仅保证 `version` 递增一致，不做乐观锁 |

## 五、变更记录

| 日期 | 变更 | 说明 |
| --- | --- | --- |
| 2026-10 | 建立设计基线 | 汇总已定决策 D-01…D-18，明确文档职责与引用关系 |
| 2026-10 | 补充 M05 确认与登录落点 | 新增 `api.md 5.6` 确认准备稿（Issue #28）；新增 D-19 登录落点与全局外壳 |
| 2026-10 | 建立协作与分支规则 | 新增 `collaboration-rules.md`：三流分工、先合 `develop`、定期同步、`develop → main` 推进 |
| 2026-10 | 模型密钥用户自带 | 新增 D-20：`/me/settings/model` BYOK + Fernet 加密存库 + 用户>全局优先级 |
| 2026-10 | BYOK 生效来源与前端设置页 | `api.md 2.5` 响应新增 `llm_source`/`embedding_source`；前端新增模型设置页（用户配置 > 服务端默认） |
| 2026-10 | 模型配置安全加固 | 新增 D-21：弱 `SECRET_KEY` 拒绝、密钥轮换、`api_base` SSRF 校验、全局密钥不脱敏回显 |
| 2026-10 | BYOK 默认禁止全局回退 | 新增 D-22：未配置用户不再自动使用全局 Key；新增 `MODEL_CONFIG_REQUIRED`/`MODEL_QUOTA_EXCEEDED` |
| 2026-10 | 闭环可靠性修复 | 归档只读、材料失败状态、来源/删除一致性、问答范围与受限记录上下文、任务/问题状态机 |
| 2026-10 | 纪要融合与记录标记 | 记录新增 `marker_type`；纪要生成融合当前会议资料与实际参与记录的标记，记录 `source_material_ids`；迁移 `0013` |
| 2026-10 | 纪要模板 | 新增 `standard` / `concise` / `task_list` 模板并记录 `meeting_minutes.template`；重新生成不覆盖已确认纪要；迁移 `0014` |
| 2026-10 | 按用途模型路由 | `user_model_configs.llm_purpose_models` 覆盖准备/问答/纪要/提取模型名；共享 LLM 地址与密钥；迁移 `0015` |
| 2026-10 | 个人知识库核心 | 独立 `knowledge_documents` / `knowledge_chunks`；上传、解析、索引、检索、删除；迁移 `0016` |
| 2026-10 | 知识库接入问答 | 新增 `context_scope=knowledge_base`，仅检索知识库；来源新增 `document_id`/`document_name` |
| 2026-10 | 记忆中心 | 用户显式维护角色/场景/表达偏好/默认纪要模板；按用途注入准备/纪要/问答 Prompt；迁移 `0017` |
| 2026-10 | 本地会议工作区 | 浏览器授权目录后导入资料、导出最新纪要 DOCX；无后端路径访问，无数据库迁移 |
| 2026-10 | 音频导入与转写 | 音频上传、同步 ASR、转写修订、确认生成记录；迁移 `0018`；实时 ASR 暂不做 |
