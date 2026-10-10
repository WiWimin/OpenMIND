# AI 会议个人助理 —— 模块详细任务文档

> **文档目的**：为 OpenMIND 的 M01–M10 提供模块级详细技术说明，回答每个模块「在闭环中做什么、和其他模块怎么配合、怎么落地、如何验收」。
>
> **不规定**：前端页面视觉细节、AI 提示词内容、RAG 检索算法参数、服务层内部函数级拆分。这些由负责成员自行决定。
>
> **技术栈**：Vue 3 + TypeScript + Vite（前端） · Python + FastAPI + Pydantic（后端） · SQLAlchemy + Alembic（ORM/迁移） · PostgreSQL + pgvector（数据层） · 本地文件目录 `storage/`（MVP 文件存储）。

## 本文的引用与标注约定

- **契约引用**：接口以 `docs/api.md` 为准，数据以 `docs/database.md` 为准。本文**只引用其章节号，不复制字段定义**；若与契约冲突，以契约为准并同步修正本文。
  - `api.md` 章节：`一 统一约定` / `二 用户认证` / `三 会议管理` / `四 会议资料与会议记录` / `五 AI 应用` / `六 行动项与个人任务` / `七 未解决问题` / `八 接口联调顺序`。
  - `database.md` 章节：`一 数据设计原则` / `二 主键与通用字段约定` / `三 核心数据实体` / `四 数据关系(E-R)` / `五 共享状态与枚举` / `六 索引与约束建议` / `七 删除与数据一致性策略` / `八 数据库与迁移协作规范` / `九 基础设施`。
  - `design-baseline.md`：文档职责与决策日志（D-01…D-18）；`ai-design.md`：AI 调用/解析/RAG/重试/幂等链路。
- **状态标注**：全文用 `[已实现]`（M00 已验收部分）、`[规划]`（本文计划、代码尚未实现）、`[待确认]`（仓库契约未明确，联调前须团队定）区分事实与计划，避免把「计划」误读为「现状」。
- **任务编号**：`Mxx-NN` 两级编号为本文件约定。仓库现有编号仅到 `M00-01…M00-09`（见 `module-task-plan.md`），M01 及以后无子任务编号，本文补齐。
- **负责人**：A 系统与业务后端；B AI 后端；C 前端与体验。分工依据 `module-task-plan.md` 与 `CODEOWNERS`。
- **未明字段/参数**：仓库契约未枚举的字段或参数，一律标 `[待确认]` 并以最终 OpenAPI 为准，本文不凭空定义。

---

## 目录

- [一、整体架构与模块总览](#一整体架构与模块总览)
- [二、通用约定](#二通用约定)
- [三、模块详情](#三模块详情)
  - [M00 工程基础](#m00-工程基础)（精简）
  - [M01 用户认证](#m01-用户认证)
  - [M02 会议管理](#m02-会议管理)
  - [M03 会议资料管理](#m03-会议资料管理)
  - [M04 AI 基础服务与 RAG](#m04-ai-基础服务与-rag)
  - [M05 会前准备](#m05-会前准备)
  - [M06 会中记录与问答](#m06-会中记录与问答)
  - [M07 会议纪要与行动项](#m07-会议纪要与行动项)
  - [M08 个人任务管理](#m08-个人任务管理)
  - [M09 未解决问题管理](#m09-未解决问题管理)
  - [M10 测试部署与交付](#m10-测试部署与交付)（精简）
- [四、附录](#四附录)

---

## 一、整体架构与模块总览

### 1.1 技术架构

```text
┌───────────────────────────────────────────────────────────────┐
│                            浏览器                               │
│   登录 │ 会议列表 │ 会议工作区 │ 会前准备 │ 纪要 │ 任务 │ 问题    │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTP / JSON（/api/v1）
┌───────────────────────────────▼───────────────────────────────┐
│                       前端层（Vue 3 + TS）                       │
│  views/（页面） · components/（组件） · stores/（Pinia 状态）      │
│  api/（axios 封装，统一错误规范化） · router/ · types/            │
│  只负责展示、收集输入、交互与调用 API；不访问数据库、不持有密钥        │
└───────────────────────────────┬───────────────────────────────┘
                                │ /api/v1
┌───────────────────────────────▼───────────────────────────────┐
│                      后端层（FastAPI）                           │
│  api/v1/          路由、依赖注入、响应组装（不含业务规则）           │
│  services/        业务规则、状态流转、权限归属校验                   │
│  repositories/    数据库查询与持久化                              │
│  schemas/         Pydantic 请求/响应模型                         │
│  models/          SQLAlchemy ORM 模型                           │
│  ai/              LLM / Embedding / RAG / Prompt / 解析 / 提取     │
│  core/            配置、日志、统一异常                             │
└───────────────────────────────┬───────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────┐
│    数据层：PostgreSQL + pgvector  +  文件目录 storage/（MVP）      │
└───────────────────────────────────────────────────────────────┘
```

> 分层职责详见 `architecture.md`。当前 `[已实现]` 的仅 M00 骨架（健康检查、配置、异常、迁移、CI）；其余业务目录均为 `[规划]` 空骨架。

### 1.2 分层边界与职责

| 层 | 只做 | 不做 |
| --- | --- | --- |
| 前端 `views/components/stores` | 展示、交互、收集输入、调用 API、前端状态 | 不直接访问数据库；不持有模型密钥；不自行改写业务状态 |
| 路由 `api/v1/` | HTTP 解析、依赖注入（当前用户、DB 会话）、响应组装 | 不写业务规则；不直接拼 SQL |
| 业务 `services/` | 归属校验、状态机、候选/确认流转、行动项转任务 | 不实现 AI 推理；不直接暴露 ORM 给前端 |
| 数据 `repositories/` | 查询与持久化，按 `user_id`/`meeting_id` 过滤 | 不决定业务状态 |
| AI `ai/` | 生成候选结果、语义检索、内容整理、解析与提取 | 不自行创建/完成/撤销任务；不覆盖用户原文 |

> **原则**（`database.md 一 数据设计原则`）：个人数据隔离；原始数据与 AI 结果分离；候选与确认分离；业务状态由后端控制；密钥只在服务端环境变量。

### 1.3 模块总览与依赖关系

```text
        M00 工程基础
             │
             ▼
        M01 用户认证 ──────────┐
             │                 │
             ▼                 │
        M02 会议管理 ◄─────────┘（所有业务模块的归属根）
             │
   ┌─────────┼───────────────┬───────────────┬──────────────┐
   ▼         ▼               ▼               ▼              ▼
 M03 资料  M05 会前准备    M06 记录+问答   M07 纪要+行动项  M09 问题
   │         │               │               │
   ▼         │               │               │
 M04 AI基础/RAG ◄──────────┴───────────────┘
                                   │
                                   ▼
                             M08 个人任务
                                   │
                                   ▼
                         M10 测试·部署·交付
```

依赖来源：`module-task-plan.md` 模块总览「依赖」列。自上而下，下层产出是上层输入；`M04` 被 M05/M06/M07 复用；`M02` 是所有数据隔离入口。

### 1.4 数据流向主线（MVP 闭环）

```text
创建会议(M02) → 导入资料(M03) → 解析/索引(M04) → 会前准备(M05)
    → 会中记录与问答(M06) → 生成纪要(M07) → 提取行动项/问题(M07/M09)
    → 行动项确认并转任务(M07/M08) → 任务跟进(M08)
```

### 1.5 目录结构与模块映射

> `[已实现]`=M00 已落地；`[规划]`=目录/文件为空骨架，待实现。

| 模块 | 后端归属 | 前端归属 |
| --- | --- | --- |
| M01 认证 | `api/v1/auth.py` `[规划]`、`services/auth_service.py` `[规划]` | `views/auth/` `[规划]`、`api/auth.ts` `[规划]`、`stores/` `[规划]` |
| M02 会议 | `api/v1/meetings.py` `[规划]`、`services/meeting_service.py` `[规划]` | `views/meetings/` `[规划]`、`api/meetings.ts` `[规划]` |
| M03 资料 | `api/v1/materials.py` `[规划]`、`services/material_service.py` `[规划]`、`ai/parsers/` `[规划]` | 会议详情材料区、`api/materials.ts` `[规划]` |
| M04 AI/RAG | `ai/llm/`、`ai/embeddings/`、`ai/rag/`、`ai/chat/`、`ai/prompts/` `[规划]` | 无独立页面，服务于 M05/M06/M07 |
| M05 会前准备 | `api/v1/preparations.py` `[规划]`、`ai/preparation/` `[规划]` | `views/preparation/` `[规划]`、`api/preparations.ts` `[规划]` |
| M06 记录+问答 | `api/v1/records.py`、`api/v1/ai_chat.py`、`ai/chat/` `[规划]` | `views/workspace/` `[规划]`、`api/records.ts` `[规划]` |
| M07 纪要+行动项 | `api/v1/minutes.py`、`api/v1/action_items.py`、`ai/minutes/`、`ai/extraction/` `[规划]` | `views/minutes/` `[规划]`、`api/minutes.ts` `[规划]` |
| M08 任务 | `api/v1/tasks.py` `[规划]`、`services/task_service.py` `[规划]` | `views/tasks/` `[规划]`、`api/tasks.ts` `[规划]` |
| M09 问题 | `api/v1/issues.py` `[规划]`、`services/issue_service.py` `[规划]`、`ai/extraction/` `[规划]` | `views/issues/` `[规划]`、`api/issues.ts` `[规划]` |

- `[已实现]`：`api/v1/health.py`、`core/config.py`、`core/exceptions.py`、`db/session.py`、`db/base.py`、`alembic/`、前端 `api/client.ts`、`api/health.ts`、`router/index.ts`、`types/`。
- `frontend/src/stores/`、`layouts/` 当前仅 `.gitkeep`；各 `views/*/` 亦仅 `.gitkeep`，`[规划]` 待填充。
- 前端 axios 实例与错误规范化见 `frontend/src/api/client.ts`（`[已实现]`）。

### 1.6 三人协作边界

| 角色 | 职责 | 主要模块 |
| --- | --- | --- |
| A | 系统与业务后端：工程骨架、认证、会议 CRUD、任务、数据库与迁移、权限、部署 | M00、M01、M02、M08、M09（业务）、M10 |
| B | AI 后端：解析、Embedding、RAG、Prompt、会前准备、纪要/行动项/问题提取 | M03（AI）、M04、M05、M06（AI）、M07、M09（AI） |
| C | 前端与体验：Vue 页面、状态交互、前端测试 | 各模块前端、M01–M09 |

**协作规则**：
1. **先接口，后并行**：数据模型与 API 契约先评审，前后端再并行实现。
2. 涉及数据库结构的改动必须附带 Alembic 迁移；主 schema 与迁移由 A 统一合并，B 的 AI 领域字段先提交变更说明（`database.md 八 数据库与迁移协作规范`）。
3. 前端只依赖 `api.md` 的请求/响应模型，不依赖数据库字段或 ORM 内部结构。
4. 所有人参与接口评审、代码审查与端到端测试。

---

## 二、通用约定

### 2.1 与现有文档的关系

- 接口路径、请求/响应字段、状态码、错误码以 `api.md` 为准；本文只引用章节号，不复制字段定义。
- 表结构、字段、状态枚举、权限与删除策略以 `database.md` 为准。
- 测试分层与命令以 `testing.md` 为准。
- 若本文与 `api.md`/`database.md` 冲突，以契约文档为准并同步修正本文。

### 2.2 统一约定速查（以 `api.md 一 统一约定` 为准）

以下为 `api.md 一` **实际约定**，不含本文臆造：

- **API 前缀**：`/api/v1`（`backend/app/core/config.py:16` `[已实现]`）。
- **数据格式**：JSON；文件上传 `multipart/form-data`。
- **成功响应**：强制 `{ "status": "success", "data": ... }`（`api.md 一.1`）。
- **错误响应**：`{ "status": "error", "error_code", "message", "retryable" }`；错误码见 `api.md 一.3`。
- **ID**：由后端生成，带前缀字符串（`database.md 二`）。
- **身份认证**：`Authorization: Bearer <access_token>`（`api.md 一`）。
- **分页**：`page`/`page_size`/`total`/`total_pages` + `data.items`/`data.pagination`（`api.md 一.4`）。
- **PATCH 语义**：见 `api.md 一.5`。
- **越权**：统一 `404 RESOURCE_NOT_FOUND`（`api.md 一.6`）。
- **时间**：ISO 8601 带时区（`api.md 一.7`）。

库内以 **UTC** 存储、接口返回带时区 ISO 8601（已定，`design-baseline.md` D-11）。

### 2.3 AI 能力层统一规范

所有 AI 能力集中在 `backend/app/ai/`，对外只通过 service 层调用，禁止与会议 CRUD 混写。

| 子目录 | 职责 | 主要使用模块 |
| --- | --- | --- |
| `ai/llm/` | 大模型调用封装（超时、重试、结构化输出） | M05、M06、M07 |
| `ai/embeddings/` | 文本向量化 | M04 |
| `ai/rag/` | 检索（按用户权限限定范围） | M04、M06 |
| `ai/prompts/` | Prompt 模板集中管理 | M05、M06、M07 |
| `ai/parsers/` | 文件解析（PDF/Word/TXT 等） | M03 |
| `ai/preparation/` | 会前摘要与清单生成 | M05 |
| `ai/minutes/` | 纪要生成 | M07 |
| `ai/extraction/` | 行动项/问题提取 | M07、M09 |

**统一约束**：
- AI 输出默认是「草稿/候选」，不得因模型返回成功即视为用户确认。
- 检索必须先按当前用户限定范围，禁止全库相似度检索后再过滤。
- 模型异常转译为统一错误码（如 `MODEL_TIMEOUT`/`MODEL_OUTPUT_INVALID`），不向前端泄露原始异常或提示词。

### 2.4 统一验收口径

- 每个模块必须具备：正常流程可走通、越权访问被拒、非法状态流转报明确错误码、涉及表有迁移。
- 提交前：后端 `cd backend && ruff check . && pytest`；前端 `cd frontend && npm run typecheck && npm run lint && npm run test`（`testing.md`、`.github/workflows/ci.yml`）。
- 每个模块的验收标准见第三章对应小节；全局验收见 `requirements.md`。

---

## 三、模块详情

> 格式统一为：模块概述 / 业务场景 / 与其他模块的关系 / 技术栈与边界理由 / 后端子模块 / 前端子模块 / 数据与状态 / 任务拆分与验收 / 风险与注意事项。M00、M10 采用精简结构。

---

### M00 工程基础

**负责人**：A 主导，全员参与　**优先级**：P0　**依赖**：无

`[已实现]`，验收见 `docs/M00-acceptance.md`。任务见 `module-task-plan.md` 的 `M00-01…M00-09`：

| 编号 | 任务 | 状态 |
| --- | --- | --- |
| M00-01 | GitHub 仓库、main/develop 分支 | 已完成 |
| M00-02 | PR/Issue 模板与分支规范 | 已完成 |
| M00-03 | Vue 3 + TS + Vite 初始化 | 已完成 |
| M00-04 | FastAPI + 健康检查 | 已完成 |
| M00-05 | PostgreSQL + pgvector + Docker Compose | 已完成 |
| M00-06 | SQLAlchemy / Alembic / Pydantic | 已完成 |
| M00-07 | 环境变量与 `.env.example` | 已完成 |
| M00-08 | 验证模型 API 与 Embedding API 连通性 | **未完成**（B，后续阶段，转入 M04-06） |
| M00-09 | 开发启动文档 | 已完成 |

> 交付物：`backend/` 可启动并返回健康状态、`frontend/` 可构建、数据库迁移 `0002_enable_pgvector` 生效、CI 绿（`Backend ruff+pytest`、`Frontend typecheck+lint+test+build`）。

---

### M01 用户认证

**负责人**：A（后端），C（前端）　**优先级**：P0　**依赖**：M00

#### 1. 模块概述

提供注册、登录、退出与「当前用户」识别，是全部业务接口权限过滤的前提。产出：可被依赖注入识别的当前用户上下文，供 M02–M09 做归属校验。

#### 2. 业务场景

| 场景 | 说明 | 触发入口 |
| --- | --- | --- |
| 注册 | 创建账户 | 登录页「注册」 |
| 登录 | 换取访问凭证 | 登录页 |
| 退出 | 清除本地凭证 | 全局「退出」 |
| 获取当前用户 | 展示并验证登录态 | 路由守卫 / 个人中心 |

#### 3. 与其他模块的关系

M01 为 M02–M09 提供 `current_user`（依赖注入），是数据隔离的根。

**接口契约**（`api.md 二 用户认证`）：

| 方法 | 路径 |
| --- | --- |
| POST | `/api/v1/auth/register` |
| POST | `/api/v1/auth/login` |
| POST | `/api/v1/auth/logout` |
| GET | `/api/v1/auth/me` |

#### 4. 技术栈与边界理由

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI + Pydantic + 密码哈希（`passlib[bcrypt]`，`design-baseline.md` D-03） |
| 前端 | Vue 3 + Pinia + vue-router |

> 认证上下文由后端维护；前端仅持有访问凭证并注入请求头，不解析凭证内容。

#### 5. 后端子模块

- **5.1 用户表与迁移**：`users`（`database.md 三` User 行）表 + Alembic 迁移。
- **5.2 密码哈希与 schemas**：注册/登录/当前用户 Pydantic 模型；密码不落明文、接口不返回哈希。
- **5.3 auth repository + service**：注册（`name` 唯一）、登录校验、当前用户查询。
- **5.4 认证依赖注入**：`get_current_user`，供各路由复用；认证机制为 `Authorization: Bearer <access_token>`（`api.md 一`/`二`）。
- **5.5 路由**：`api/v1/auth.py` 暴露四个接口。

#### 6. 前端子模块

- **6.1 登录/注册页**（`views/auth/`）：表单校验、错误按 `error_code` 提示。
- **6.2 路由守卫 + token 注入**（`router/` + `api/client.ts` 拦截器）：未登录跳转登录页；请求头注入凭证。
- **6.3 auth store**（`stores/`）：登录态、当前用户、token 持久化。

#### 7. 数据与状态

- 表：`users`（`database.md 三`）；约束：`name` 唯一（`database.md 三`）。
- 状态：`status`（`active`/`disabled`，`database.md 三`）。

#### 8. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M01-01 | `users` 表 + Alembic 迁移 | A | M00-06 | 迁移成功，字段符合 `database.md 三` |
| M01-02 | 密码哈希 + User schemas | A | M01-01 | 不存明文；不返回哈希 |
| M01-03 | auth repository + service | A | M01-01 | 注册唯一性、登录校验正确 |
| M01-04 | `get_current_user` 依赖注入 | A | M01-03 | 未登录返回 `AUTH_REQUIRED` |
| M01-05 | `api/v1/auth.py` 路由 | A | M01-04 | 四接口可用，响应符合统一结构 |
| M01-06 | 登录/注册页 + 表单校验 | C | M01-05 | 校验与错误提示正确 |
| M01-07 | 路由守卫 + token 注入 | C | M01-04 | 未登录跳登录；凭证正确注入 |
| M01-08 | auth store | C | M01-07 | 登录态持久化与恢复正确 |
| M01-09 | 认证集成测试 | A | M01-05 | 含未登录 401、重复注册、越权 |

#### 9. 风险与注意事项

- 认证机制（Bearer）与登录标识（`name`）已在 `api.md` 一/二 统一；前端拦截器按 Bearer 注入。
- 密码哈希采用 `passlib[bcrypt]`（`design-baseline.md` D-03）。

---

### M02 会议管理

**负责人**：A（后端业务），C（前端）　**优先级**：P0　**依赖**：M00、M01

#### 1. 模块概述

会议是所有业务数据的**归属根**。M02 提供会议列表、创建、详情、编辑、删除、归档，并确立「个人数据隔离」的落地方式：后续材料、记录、准备稿、纪要、行动项、问题的读写都先验证其所属会议属于当前用户。

#### 2. 业务场景

| 场景 | 说明 | 触发入口 |
| --- | --- | --- |
| 创建会议 | 录入标题、可选主题与时间 | 列表页「新建会议」 |
| 浏览会议列表 | 分页查看本人会议 | 首页 / 侧边导航 |
| 查看会议详情 | 查看基础信息并进入子区域 | 列表项点击 |
| 编辑会议 | 修改标题/主题/时间 | 详情页「编辑」 |
| 归档会议 | 归档（MVP 建议只读） | 详情页「归档」 |
| 删除会议 | 删除会议及关联数据 | 详情页「删除」 |

#### 3. 与其他模块的关系

```text
M01 认证 ──提供 current_user──▶ M02 会议管理
                                   │
                        提供「会议属于当前用户」校验
                                   ▼
  M03 资料 · M05 准备 · M06 记录/问答 · M07 纪要/行动项 · M08 任务 · M09 问题
```

**接口契约**（`api.md 三 会议管理`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings` | 会议列表 |
| POST | `/api/v1/meetings` | 创建会议 |
| GET | `/api/v1/meetings/{meeting_id}` | 会议详情 |
| PATCH | `/api/v1/meetings/{meeting_id}` | 编辑会议 |
| DELETE | `/api/v1/meetings/{meeting_id}` | 删除会议及关联数据 |
| POST | `/api/v1/meetings/{meeting_id}/archive` | 归档会议 |

**对其他模块暴露的能力**（`services/` 内部复用，不对外）：
- `get_owned_meeting(meeting_id, current_user)`：不存在或不属于当前用户时抛 `RESOURCE_NOT_FOUND`（统一 404，`api.md 一.6`）。

#### 4. 技术栈与边界理由

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Pinia + vue-router |
| 后端 | FastAPI + Pydantic + SQLAlchemy |

> **归属校验放 `services/`**：M03–M09 复用同一套会议归属判断，放 service 层可被所有下级 service 调用，避免各路由重复实现产生权限缺口。

#### 5. 后端子模块

- **5.1 会议 CRUD 服务**（`services/meeting_service.py`）：列表、创建、详情、编辑、删除、归档。
  - 列表按 `user_id = current_user.user_id` 过滤；分页遵循 `api.md 一.4`。
  - 创建 `user_id` 由服务端从认证上下文填充，不接受请求体传入；默认状态 `scheduled`（`database.md 三`）。
  - 编辑仅允许 `title/topic/meeting_time`；服务端管理字段不可改。
- **5.2 归档服务**：校验归属后归档，写入 `status=archived` 与 `archived_at`（`database.md 三`）；MVP 归档后只读（不允许编辑或再触发 AI 生成）。
- **5.3 删除与关联清理**：遵循 `database.md 七`（删除与数据一致性策略），须在事务中显式执行，不依赖隐式级联。

#### 6. 前端子模块

##### 6.1 路由

| 路径 | 名称 | 组件 |
| --- | --- | --- |
| `/meetings` | `meetings` | `views/meetings/MeetingListView.vue` |
| `/meetings/:meetingId` | `meeting-detail` | `views/meetings/MeetingDetailView.vue` |

##### 6.2 列表筛选与分页前后端对应

| 层 | 实现 | 说明 |
| --- | --- | --- |
| 前端 API | `api/meetings.ts` 的 `listMeetings(params)` | 参数默认仅分页（`api.md 一.4`）；`status/keyword/time` 筛选在实现对应逻辑后开放（`api.md 三.1`） |
| 前端状态 | `stores/meetings` 的 `items/pagination/filters/loading/error` | `[规划]` |
| 后端 service | `services/meeting_service.py` 列表按 `user_id` 过滤 + 分页 | `[规划]` |
| 后端 repository | 按 `user_id` 过滤的查询与持久化 | `[规划]` |

**测试标准**（M02-08 / M02-12）：
- 分页边界：`page` 从 1 开始；`page_size` 默认 20、最大 100（`api.md 一.4`）。
- 越权：用户 A 请求用户 B 的会议详情/编辑/删除均返回 `404 RESOURCE_NOT_FOUND`（`api.md 一.6`）。
- 空态/错误态：空列表、非法参数、后端错误均有友好前端提示。

##### 6.3 会议列表页（`MeetingListView.vue`）

- **组件**：`MeetingList`、`MeetingCard`、`Pagination`、`CreateMeetingButton`（筛选组件：MVP 支持 `status`，`design-baseline.md` D-17）。
- **交互**：进入即加载；翻页重新请求；点击进入详情；「新建」打开表单。
- **Pinia**：`items/pagination/filters/loading/error`。
- **所调 API**：`GET /meetings`、`POST /meetings`。

##### 6.4 会议详情页（`MeetingDetailView.vue`）

- **组件**：`MeetingHeader`、`MeetingTabs`（材料/准备/记录/纪要/任务/问题子区域占位）、`ConfirmDialog`。
- **交互**：加载基础信息；「编辑/归档/删除」操作；各 Tab 懒加载对应模块组件。
- **Pinia**：`current/loading/error`。
- **所调 API**：`GET/PATCH/DELETE /meetings/{id}`、`POST /meetings/{id}/archive`。

##### 6.5 会议表单（`components/MeetingFormDialog.vue`）

- **字段**：`title`（必填）、`topic`、`meeting_time`（可选）。
- **所调 API**：`POST /meetings`（创建）、`PATCH /meetings/{id}`（编辑）。

#### 7. 数据与状态

- 表：`meetings`（`database.md 三` Meeting 行，主要字段 `meeting_id/user_id/title/topic/meeting_time/status`）。
- **状态枚举**（`database.md 五` Meeting 行）：MVP 仅 `scheduled`、`archived`（`in_progress`/`completed` 预留、不实现）。
- **MVP 实际状态**：与 `api.md 三` 一致——仅 `scheduled`/`archived`；前端只暴露可触发的操作，不展示开始/完成。
- 时间戳/归档列：`meetings` 含 `created_at`/`updated_at`/`archived_at`（`database.md 三`）。

#### 8. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M02-01 | `meetings` 表 + Alembic 迁移 | A | M00-06 | 迁移成功，字段符合 `database.md 三` |
| M02-02 | Meeting schemas（创建/更新/响应） | A | M02-01 | 校验与字段符合 `api.md 三` |
| M02-03 | 会议 repository（按 user_id 过滤） | A | M02-01 | 单元测试覆盖过滤 |
| M02-04 | `meeting_service`：CRUD + 状态机 + 归属校验 | A | M02-02、M02-03 | 越权被拒；非法流转报明确错误码 |
| M02-05 | `api/v1/meetings.py` 路由与依赖注入 | A | M02-04 | OpenAPI 自解释；统一响应结构 |
| M02-06 | 归档接口与只读约束 | A | M02-04 | 归档后编辑被拒 |
| M02-07 | 删除接口与关联清理 | A | M02-04 | 事务内清理，符合 `database.md 七`（删除与数据一致性策略） |
| M02-08 | 会议列表页 + 分页 | C | M02-05 | 列表/翻页可用；空态/错误态友好 |
| M02-09 | 会议详情页 + Tab 占位 | C | M02-05 | 加载基础信息；操作按钮可用 |
| M02-10 | 会议表单弹窗 | C | M02-05 | 校验正确；按 `error_code` 提示 |
| M02-11 | 路由接入 + 导航守卫 | C | M01-07 | 未登录跳转登录页 |
| M02-12 | 接口集成测试（含跨用户隔离） | A | M02-05 | 用户 A 不能读写用户 B 的会议 |

#### 9. 风险与注意事项

- 状态范围：MVP 只暴露实际可实现的状态，不在前端展示无法触发的操作。
- 删除策略见 `database.md 七`；归档只读规则见 `api.md 三.6`。
- 越权状态码统一为 `404 RESOURCE_NOT_FOUND`（`api.md 一.6`）。
- 详情页只消费 `api.md` 字段，不依赖数据库内部字段。

---

### M03 会议资料管理

**负责人**：B（AI 解析），A（集成/上传/迁移），C（前端）　**优先级**：P0　**依赖**：M02

#### 1. 模块概述

用户上传会议材料，后端登记文件、解析文本并做索引准备，供会前准备与问答检索使用。产出：可追溯的会议材料及其解析状态。

#### 2. 业务场景

| 场景 | 说明 | 触发入口 |
| --- | --- | --- |
| 上传材料 | 上传单个文件并登记 | 会议详情「材料」区 |
| 查看材料 | 查看材料与处理状态 | 材料列表/详情 |
| 删除材料 | 删除文件及关联索引 | 材料详情「删除」 |

#### 3. 与其他模块的关系

M03 依赖 M02（会议归属）；M03 的解析文本/分块供 M04 检索、M05 准备、M06 问答消费。

**接口契约**（`api.md 四 会议资料与会议记录`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/materials` | 上传材料 |
| GET | `/api/v1/materials/{material_id}` | 查看材料及处理状态 |
| DELETE | `/api/v1/materials/{material_id}` | 删除资料及关联索引 |

> `api.md 四.3` 已提供「材料列表」接口（标注 `[提案]`），会议详情页材料列表按该接口实现，待团队确认后转正式。

#### 4. 技术栈与边界理由

| 层 | 技术 |
| --- | --- |
| 后端（上传/登记） | FastAPI + 本地 `storage/`（`config.storage_dir`、`max_upload_mb`） |
| 后端（解析） | `ai/parsers/`（PDF/Word/TXT 等，具体解析库由 B 定） |

> 上传与登记属业务 CRUD（A）；文本解析属 AI 能力层（B），二者经 `processing_status` 解耦。

#### 5. 后端子模块

- **5.1 材料表与迁移**：`meeting_materials`（`database.md 三` MeetingMaterial 行）。
- **5.2 上传存储与校验**：文件落 `storage/`，校验类型/大小（`config.max_upload_mb` `[已实现]`；白名单 `pdf/docx/txt`，`design-baseline.md` D-16）。
- **5.3 schemas/repository/service**：归属校验（材料所属会议属于当前用户）。
- **5.4 路由**：`api/v1/materials.py`。
- **5.5 解析管线**（`ai/parsers/`，B）：解析文本、维护 `processing_status` 流转（`database.md 五` Material 行：`uploaded/processing/processed/failed`）。

#### 6. 前端子模块

- **6.1 会议详情材料区**：上传、材料列表（`api.md 四.3` [提案]）、状态展示。
- **6.2 材料状态轮询/刷新**：`processing_status` 展示。
- **6.3 API 封装**：`api/materials.ts`。

#### 7. 数据与状态

- 表：`meeting_materials`（`database.md 三`）；状态：`uploaded/processing/processed/failed`（`database.md 五`）。

#### 8. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M03-01 | `meeting_materials` 表 + 迁移 | A | M02-01 | 字段符合 `database.md 三` |
| M03-02 | 上传存储与校验 | A | M03-01 | 类型/大小校验生效 |
| M03-03 | schemas/repository/service | A | M03-01 | 越权被拒 |
| M03-04 | `api/v1/materials.py` 路由 | A | M03-03 | 上传/查看/删除可用 |
| M03-05 | 解析管线（`ai/parsers/`）+ 状态流转 | B | M03-04 | 解析成功/失败状态正确 |
| M03-06 | 材料区前端（上传/列表/状态） | C | M03-04 | 上传与状态展示可用 |
| M03-07 | 材料列表接口（`api.md 四.3` [提案]） | A | M03-04 | 实现后 OpenAPI 同步 |
| M03-08 | 解析与越权测试 | A/B | M03-05 | 解析失败态与跨用户隔离正确 |

#### 9. 风险与注意事项

- 材料列表接口已提案（`api.md 四.3`），待团队确认；上传白名单为 `pdf/docx/txt`、≤ `MAX_UPLOAD_MB`（D-16）。
- 删除材料须同步清理分块/索引（`database.md 七`（删除与数据一致性策略））。

---

### M04 AI 基础服务与 RAG

**负责人**：B（集成 A）　**优先级**：P0　**依赖**：M03

#### 1. 模块概述

封装大模型调用、Embedding、文本切分与向量检索，被 M05/M06/M07 复用；无独立对外接口，也不自行决定业务动作。

#### 2. 与其他模块的关系

M04 消费 M03 的解析文本；为 M05（准备）、M06（问答）、M07（纪要/提取）提供底层能力。

#### 3. 技术栈与边界理由

| 层 | 技术 |
| --- | --- |
| LLM | `ai/llm/`（超时、重试、结构化输出） |
| Embedding | `ai/embeddings/`（阿里百炼 `text-embedding-v3`，维度 **1024**；`config.embedding_model/dim`） |
| RAG | `ai/rag/`（权限内检索）+ `ai/chat/`、`ai/prompts/` |

> 检索必须先按当前用户限定范围（`document_chunks → meeting_materials → meetings`），禁止全库相似度检索后再过滤。

#### 4. 后端子模块

- **4.1 LLM 封装**（`ai/llm/`）
- **4.2 Embedding 客户端**（`ai/embeddings/`）
- **4.3 `document_chunks` 表 + 迁移**（A 迁移，B 提字段）
- **4.4 切分与向量化管线**（B）
- **4.5 RAG 检索**（`ai/rag/`，B）
- **4.6 落地 `M00-08` 连通性验证**（B）

#### 5. 数据与状态

- 表：`document_chunks`（`database.md 三` DocumentChunk 行）；向量维度固定 **`vector(1024)`**（模型 `text-embedding-v3`）。

#### 6. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M04-01 | `ai/llm/` 封装 | B | M00-07 | 超时/重试/结构化输出可用 |
| M04-02 | `ai/embeddings/` 客户端 | B | M00-07 | 向量生成可用 |
| M04-03 | `document_chunks` 表 + 迁移 | A | M03-01 | 字段符合 `database.md 三` |
| M04-04 | 切分 + 向量化管线 | B | M04-02、M04-03 | 分块含来源、向量可存 |
| M04-05 | `ai/rag/` 权限内检索 | B | M04-04 | 只检索当前用户数据 |
| M04-06 | `M00-08` 连通性验证 | B | M04-01、M04-02 | 模型/Embedding 连通 |
| M04-07 | 跨用户检索隔离测试 | B | M04-05 | 无法检索他人分块 |

#### 7. 风险与注意事项

- embedding 维度已固定为 1024；向量索引类型（HNSW/IVFFlat）待数据量确定后选择（`database.md 六`）。
- 检索必须经权限过滤，是数据隔离的底线。

---

### M05 会前准备

**负责人**：B（AI），C（前端），集成 A　**优先级**：P0　**依赖**：M02、M03、M04

#### 1. 模块概述

基于会议材料生成会前摘要与准备清单（草稿），用户可编辑；结果以草稿存在，不自动视为确认。

#### 2. 与其他模块的关系

依赖 M02（会议）、M03（材料）、M04（检索/LLM）。

**接口契约**（`api.md 五 AI 应用`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/prepare` | 生成会前摘要与清单 |
| GET | `/api/v1/meetings/{meeting_id}/preparations` | 准备稿历史 |
| GET | `/api/v1/preparations/{preparation_id}` | 准备稿详情 |
| PATCH | `/api/v1/preparations/{preparation_id}` | 编辑/确认 |

#### 3. 后端子模块

- **3.1 `preparations` 表 + 迁移**（`database.md 三` Preparation 行）
- **3.2 schemas/repository**（A）
- **3.3 摘要/清单生成**（`ai/preparation/`，B）
- **3.4 路由**（`api/v1/preparations.py`，A）

#### 4. 前端子模块

- **4.1 准备页**（`views/preparation/`）：生成、编辑、确认。
- **4.2 store + API 封装**（`stores/`、`api/preparations.ts`）。

#### 5. 数据与状态

- 表：`preparations`；状态：`generating/draft/confirmed/failed`（`database.md 五` Preparation 行）。

#### 6. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M05-01 | `preparations` 表 + 迁移 | A | M02-01 | 字段符合 `database.md 三` |
| M05-02 | schemas/repository | A | M05-01 | 越权被拒 |
| M05-03 | 摘要/清单生成 | B | M04-05 | 生成草稿可保存 |
| M05-04 | `api/v1/preparations.py` 路由 | A | M05-02、M05-03 | 生成/历史/详情/PATCH 可用 |
| M05-05 | 准备页前端 | C | M05-04 | 生成/编辑/确认流程可用 |
| M05-06 | 准备 store + API 封装 | C | M05-04 | 状态与请求正确 |
| M05-07 | 失败态与重试测试 | B | M05-03 | 生成失败状态正确 |
| M05-08 | 越权与状态测试 | A | M05-04 | 跨用户隔离 |

#### 7. 风险与注意事项

- 生成方式：MVP 同步完成，超时返回统一错误（`api.md 五.2`）。
- 版本策略：生成新增记录；编辑原地更新并 `version` 递增（`design-baseline.md` D-14）。

---

### M06 会中记录与问答

**负责人**：C（前端）、B（AI 问答）、A（后端）　**优先级**：P0　**依赖**：M02、M04

#### 1. 模块概述

会议中的手动记录（增删改查）与基于材料的 AI 问答（含来源引用），问答范围受当前用户权限限制。

#### 2. 与其他模块的关系

依赖 M02（会议）、M04（RAG）；记录/问答产出供 M07 纪要与行动项提取使用。

**接口契约**：

记录（`api.md 四`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/records` | 新增会议记录 |
| GET | `/api/v1/meetings/{meeting_id}/records` | 查询会议记录 |
| PATCH | `/api/v1/records/{record_id}` | 编辑记录 |

问答（`api.md 五`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/chat` | 会议相关问答与 RAG 检索 |
| POST | `/api/v1/meetings/{meeting_id}/organize` | 整理记录内容 |

#### 3. 后端子模块

- **3.1 `meeting_records` 表 + 迁移**（`database.md 三` MeetingRecord 行）
- **3.2 records schemas/repository/service**（A）
- **3.3 记录路由**（`api/v1/records.py`，A）
- **3.4 问答路由 + 检索**（`api/v1/ai_chat.py` + `ai/chat/`，B）

#### 4. 前端子模块

- **4.1 工作区记录页**（`views/workspace/`）：输入、列表、编辑。
- **4.2 问答面板**：提问、来源展示、`insufficient_evidence` 提示。

#### 5. 数据与状态

- 表：`meeting_records`；`record_type` 值见 `database.md 三`（`manual/transcript/imported`）。

#### 6. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M06-01 | `meeting_records` 表 + 迁移 | A | M02-01 | 字段符合 `database.md 三` |
| M06-02 | records schemas/repository/service | A | M06-01 | 越权被拒 |
| M06-03 | `api/v1/records.py` 路由 | A | M06-02 | 记录三接口可用 |
| M06-04 | 问答路由 + `ai/chat/` | B | M04-05 | 回答带来源、权限内 |
| M06-05 | 工作区记录页 | C | M06-03 | 记录增改查可用 |
| M06-06 | 问答面板 | C | M06-04 | 提问/来源/证据不足提示可用 |
| M06-07 | 记录与问答测试 | A/B | M06-03、M06-04 | 来源正确、跨用户隔离 |

#### 7. 风险与注意事项

- 记录删除接口已在 `api.md 四.11` 提出（`[提案]`），待确认是否纳入 MVP。
- 问答响应字段（`answer/sources/insufficient_evidence`）以 `api.md 五` 示例与 OpenAPI 为准。

---

### M07 会议纪要与行动项

**负责人**：B（AI 生成/提取）、A（后端业务）、C（前端）　**优先级**：P0　**依赖**：M04、M06

#### 1. 模块概述

基于记录生成纪要草稿，并提取候选行动项；行动项须用户确认后才能转任务。纪要与行动项均为「候选/草稿」，不自动视为确认。

#### 2. 与其他模块的关系

依赖 M04（LLM）、M06（记录）；行动项确认后对接 M08（任务）。

**接口契约**：

AI 生成/提取（`api.md 五`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/minutes/generate` | 生成/更新纪要 |
| POST | `/api/v1/meetings/{meeting_id}/action-items/extract` | 提取候选行动项 |

行动项业务（`api.md 六`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings/{meeting_id}/action-items` | 查询行动项 |
| PATCH | `/api/v1/action-items/{action_id}` | 编辑行动项 |
| POST | `/api/v1/action-items/{action_id}/confirm` | 确认行动项 |
| POST | `/api/v1/action-items/{action_id}/convert-to-task` | 转为任务 |

> `api.md 五.10–5.13` 已提案纪要读取/编辑/确认接口（`GET /meetings/{id}/minutes`、`GET /minutes/{id}`、`PATCH /minutes/{id}`、`POST /minutes/{id}/confirm`），待团队确认后转正式。

#### 3. 后端子模块

- **3.1 `meeting_minutes`、`action_items` 表 + 迁移**（`database.md 三` 对应行）
- **3.2 schemas/repository**（A）
- **3.3 纪要生成**（`ai/minutes/`，B）
- **3.4 行动项提取**（`ai/extraction/`，B）
- **3.5 路由**（`api/v1/minutes.py`、`api/v1/action_items.py`，A）

#### 4. 前端子模块

- **4.1 纪要页**（`views/minutes/`）：生成、展示、编辑/确认（`api.md 五.10–5.13` [提案]）。
- **4.2 行动项确认/编辑/转任务入口**。

#### 5. 数据与状态

- 表：`meeting_minutes`、`action_items`。
- 状态：纪要 `draft/confirmed`；行动项 `pending_confirmation/confirmed/converted/cancelled`（`database.md 五`）。
- **规则**：AI 提取默认 `pending_confirmation`；仅 `confirmed` 可转任务（`database.md` 候选与确认分离原则）。

#### 6. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M07-01 | `meeting_minutes`+`action_items` 表 + 迁移 | A | M06-01 | 字段符合 `database.md 三` |
| M07-02 | schemas/repository | A | M07-01 | 越权被拒 |
| M07-03 | 纪要生成 | B | M04-01 | 生成草稿可保存 |
| M07-04 | 行动项提取 | B | M04-01 | 候选状态正确 |
| M07-05 | 路由（minutes/action-items） | A | M07-02、M07-03、M07-04 | 接口符合 `api.md` |
| M07-06 | 纪要页前端 | C | M07-05 | 生成/展示可用 |
| M07-07 | 行动项确认/转任务入口前端 | C | M07-05 | 状态流转入口正确 |
| M07-08 | 候选状态与转任务前置校验测试 | A/B | M07-05 | 未确认不可转任务 |

#### 7. 风险与注意事项

- 纪要读取/编辑/确认接口已提案（`api.md 五.10–5.13`），待团队确认。
- 行动项重复提取不去重（可能产生重复候选）；转任务以 `action_id` 唯一幂等（`design-baseline.md` D-15）。
- 「候选与确认分离」是本模块底线（`database.md 一`）。

---

### M08 个人任务管理

**负责人**：A（后端），C（前端）　**优先级**：P0　**依赖**：M04、M07

#### 1. 模块概述

个人任务清单，支持从已确认行动项转换、状态流转、取消；任务须保留来源会议/行动项信息。

#### 2. 与其他模块的关系

依赖 M07（行动项转任务）；任务来源可追溯。

**接口契约**（`api.md 六`）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/tasks` | 查询任务清单 |
| GET | `/api/v1/tasks/{task_id}` | 任务详情 |
| PATCH | `/api/v1/tasks/{task_id}` | 修改任务信息/状态 |
| POST | `/api/v1/tasks/{task_id}/cancel` | 取消任务 |

（`convert-to-task` 见 M07 行动项接口）

#### 3. 后端子模块

- **3.1 `personal_tasks` 表 + 迁移**（`database.md 三` PersonalTask 行）
- **3.2 schemas/repository/service**：状态机、幂等转换、`user_id` 强制为当前用户。
- **3.3 路由**（`api/v1/tasks.py`）

#### 4. 前端子模块

- **4.1 任务列表页**（`views/tasks/`）：列表、状态筛选。
- **4.2 任务详情/状态流转/取消**。
- **4.3 store + API 封装**（`stores/`、`api/tasks.ts`）。

#### 5. 数据与状态

- 表：`personal_tasks`；状态：`todo/in_progress/completed/cancelled`（`database.md 五`）。

#### 6. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M08-01 | `personal_tasks` 表 + 迁移 | A | M07-01 | 字段符合 `database.md 三` |
| M08-02 | schemas/repository/service（状态机+幂等） | A | M08-01 | 状态流转校验、幂等 |
| M08-03 | `api/v1/tasks.py` 路由 | A | M08-02 | 接口符合 `api.md 六` |
| M08-04 | 任务列表页 | C | M08-03 | 列表/筛选可用 |
| M08-05 | 任务详情/状态/取消 | C | M08-03 | 状态流转与取消可用 |
| M08-06 | 任务 store + API 封装 | C | M08-03 | 状态与请求正确 |
| M08-07 | 越权/幂等/状态测试 | A | M08-03 | 跨用户隔离、重复转换幂等 |

#### 7. 风险与注意事项

- 转任务幂等（同行动项不重复建任务）：`personal_tasks.action_id` 唯一约束（`database.md 三`）。
- 状态流转后端校验，不接受任意字符串（`database.md 一`）。

---

### M09 未解决问题管理

**负责人**：A（后端业务）、B（AI 提取）、C（前端）　**优先级**：P1　**依赖**：M04、M06

#### 1. 模块概述

会议待跟进问题：AI 从记录中提取候选问题（B），用户维护问题状态与跟进信息（A）。**分工明确**：AI 提取归 B，问题 CRUD/状态归 A。

#### 2. 与其他模块的关系

依赖 M04（LLM）、M06（记录）。

**接口契约**：

AI 提取（`api.md 五`）：

| 方法 | 路径 | 用途 | 负责人 |
| --- | --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/issues/extract` | 提取未解决问题 | B |

问题业务（`api.md 七 未解决问题`）：

| 方法 | 路径 | 用途 | 负责人 |
| --- | --- | --- | --- |
| GET | `/api/v1/meetings/{meeting_id}/issues` | 查询问题 | A |
| PATCH | `/api/v1/issues/{issue_id}` | 修改问题状态/跟进 | A |

#### 3. 后端子模块

- **3.1 `open_issues` 表 + 迁移**（`database.md 三` OpenIssue 行）
- **3.2 issue schemas/repository/service**（A）
- **3.3 `api/v1/issues.py` 路由**（A）
- **3.4 问题提取**（`ai/extraction/`，B）

#### 4. 前端子模块

- **4.1 问题列表/编辑页**（`views/issues/`）。

#### 5. 数据与状态

- 表：`open_issues`；状态：`open/resolved/cancelled`（`database.md 五`）。

#### 6. 任务拆分与验收

| 编号 | 任务 | 负责人 | 依赖 | 验收标准 |
| --- | --- | --- | --- | --- |
| M09-01 | `open_issues` 表 + 迁移 | A | M06-01 | 字段符合 `database.md 三` |
| M09-02 | issue schemas/repository/service | A | M09-01 | 越权被拒 |
| M09-03 | `api/v1/issues.py` 路由（GET/PATCH） | A | M09-02 | 接口符合 `api.md 七` |
| M09-04 | 问题提取（`ai/extraction/`） | B | M04-01 | 提取候选问题 |
| M09-05 | 问题列表/编辑前端 | C | M09-03 | 状态流转入口正确 |
| M09-06 | 问题测试（含越权） | A | M09-03 | 跨用户隔离 |

#### 7. 风险与注意事项

- `M09` 已按 `requirements.md`/`module-task-plan.md`/`api.md` 统一为「未解决问题管理」，异常处理与部署归 M10（`design-baseline.md` D-12）。
- 问题提取同样不去重（`design-baseline.md` D-15）。

---

### M10 测试部署与交付

**负责人**：A 主导，全员参与　**优先级**：P0　**依赖**：M00–M09

精简任务：

| 编号 | 任务 | 负责人 | 验收标准 |
| --- | --- | --- | --- |
| M10-01 | 主闭环端到端测试 | 全员 | 建会→资料→准备→记录/问答→纪要→行动项→任务全流程走通 |
| M10-02 | 权限与异常专项 | 全员 | 越权、非法状态流转、AI 超时均有明确错误码 |
| M10-03 | 部署与演示交付 | A | `docker compose up` 可演示；`scripts/verify-db.ps1` 通过 |

> 端到端测试框架（Playwright 等）后续引入，见 `testing.md`；联调顺序见 `api.md 八`。

---

## 四、附录

### 4.1 模块间数据依赖速查表

| 消费者 | 依赖提供者 | 数据/能力 |
| --- | --- | --- |
| M02–M09 | M01 认证 | `current_user` 上下文 |
| M03/M05/M06/M07/M08/M09 | M02 会议 | 会议归属校验 |
| M04 | M03 资料 | 解析文本、`document_chunks` |
| M05/M06/M07 | M04 AI/RAG | LLM、Embedding、检索 |
| M07 | M06 记录 | 记录作为纪要/行动项来源 |
| M08 | M07 行动项 | 已确认行动项转任务 |
| M09 | M06 记录 | 记录作为问题提取来源 |

### 4.2 接口契约引用总表（按 `api.md` 章节）

| `api.md` 章节 | 模块 | 负责人 |
| --- | --- | --- |
| 二 用户认证 | M01 | A |
| 三 会议管理 | M02 | A |
| 四 会议资料与会议记录 | M03、M06 | A、B |
| 五 AI 应用（prepare/chat/organize/minutes/action-items/issues extract） | M05、M06、M07、M09 | B |
| 六 行动项与个人任务 | M07（行动项）、M08（任务） | A |
| 七 未解决问题 | M09 | A |

> 本文不新增接口；材料列表、纪要读取/编辑/确认已在 `api.md 四.3`、`五.10–5.13` 提出（`[提案]`）。

### 4.3 建议开发顺序

对齐 `module-task-plan.md` 六阶段与 `api.md 八` 联调顺序：

| 批次 | 范围 | 说明 |
| --- | --- | --- |
| 1 | M00、M01、M02 | 登录、会议 CRUD、权限隔离 |
| 2 | M03、M04 | 材料上传、解析、模型/检索 |
| 3 | M05 | 会前准备 |
| 4 | M06、M07 | 记录/问答、纪要、行动项 |
| 5 | M08、M09 | 任务、问题 |
| 6 | M10 | 端到端、异常、部署交付 |

### 4.4 决策与待确认清单

> 已定决策以 [`design-baseline.md`](design-baseline.md) 的 D-01…D-18 为准，此处不再重复。

**仍待确认**

| 项 | 说明 |
| --- | --- |
| `[提案]` 接口是否采纳 | 材料列表、纪要读取/编辑/确认、记录删除、行动项详情/删除（`api.md` 标注 `[提案]`） |
| MIME 嗅探 / 音频转写 | 超出当前 MVP |
| 向量索引类型 | HNSW/IVFFlat 待数据量确定 |
| 并发编辑冲突 | MVP 仅保证 `version` 递增，不做乐观锁 |
