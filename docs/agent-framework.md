# Agent 框架（轻量工作流）

> 目标：把「意图路由 → 工具/服务调用 → 确认门 → 长任务」串成可观测、可回滚的闭环，
> **不引入 LangGraph**。实现位于 `backend/app/agent/`，依赖方向为
> `api → agent → services → ai`。

## 1. 设计取舍

| 关注点 | 方案 | 原因 |
| --- | --- | --- |
| 工作流编排 | 自研声明式引擎 `Step` / `Edge` / `WorkflowRunner` | 只有顺序、条件边、重试和暂停，无需图运行时 |
| 意图路由 | 显式意图 → 规则 → LLM 兜底 → 页面先验 | 规则覆盖高频句，LLM 只处理歧义；失败不影响主流程 |
| 会话持久化 | `agent_sessions` / `agent_messages` | 服务端为事实来源，localStorage 仅作缓存/回退 |
| 长任务 | DB 队列 `async_jobs` + 独立 worker | 无 Redis/Celery；多 worker 用 `SKIP LOCKED` 认领 |
| 有副作用动作 | 待确认动作 `agent_pending_actions` | AI 只给候选，联网/转任务等必须用户批准 |
| 回滚 | `AGENT_ENABLED=false` | `/agent/*` 返回 404，前端自动回退既有链路 |

## 2. 模块结构

```
backend/app/agent/
├── intent.py       # 意图分类：显式 → 规则 → LLM → fallback
├── workflow.py     # 声明式引擎：Step/Edge/StepRetry/WaitForConfirmation
├── workflows.py    # 工作流定义：web_fallback / transcribe_to_minutes
├── tools.py        # 工具注册表：检索/回答/联网/转写/纪要/行动项/通知
├── service.py      # 会话与单轮编排、SSE、确认门、运行查询
└── __init__.py
```

- `intent.py` 不访问业务写接口，只读会议状态作为路由先验。
- `tools.py` 只调用既有 `services` / `ai`，不直接写会议 CRUD。
- `service.py` 负责归属校验（复用 `meeting_service.get_owned_meeting`）与持久化。
- 前端入口：`frontend/src/api/agent.ts`、`AgentChat.vue` 的 `backendSession` 模式。

## 3. 意图路由

优先级从高到低：

1. **显式意图**（快捷卡 `intent` 字段）：直接采用，`source=explicit`。
2. **规则**：会议纪要、行动项、整理、会前准备、知识库、联网、转写等高频句式，`source=rule`。
3. **LLM 兜底**：`intent_router` 场景结构化输出；超时/失败静默跳过。
4. **页面先验**：`preprocess` / `asr` / `minutes` 决定歧义句的默认意图；
   仍无法判断时返回 `clarify`，由前端展示澄清问题。

输出结构（`AgentIntentDecision`）：

```json
{
  "intent": "minutes_generate",
  "confidence": 0.86,
  "slots": {},
  "needs_clarification": false,
  "clarification_question": null,
  "source": "rule"
}
```

## 4. 工作流引擎语义

```python
Workflow(
    name="web_fallback",
    entry="retrieve",
    steps={
        "retrieve": Step("retrieve", "retrieve"),
        "ask_confirm": Step("ask_confirm", "request_web_confirmation"),
        "web_search": Step("web_search", "web_search", retry=StepRetry(max_attempts=2)),
        "answer": Step("answer", "answer_with_web"),
    },
    edges=(
        Edge("retrieve", "answer", lambda s: s.get("has_evidence")),
        Edge("retrieve", "ask_confirm"),
        Edge("ask_confirm", "web_search", lambda s: s.get("confirmed")),
        Edge("ask_confirm", None),
        Edge("web_search", "answer"),
        Edge("answer", None),
    ),
)
```

- **Step**：`name` + 工具名 + 可选 `StepRetry`；工具返回 dict 合并进 `state`。
- **Edge**：`from` + `to`（`None` 表示结束）+ 可选条件函数；按声明顺序取第一个为真的边。
- **重试**：只对 `retryable` 错误生效，指数退避；非可重试错误立即失败。
- **暂停**：工具抛出 `WaitForConfirmation` → 运行落 `waiting` 并登记待确认动作；
  用户批准后从 `_next_step` 继续，拒绝则以 `cancelled` 收尾。
- **预算**：`AGENT_MAX_STEPS` 与 `AGENT_MAX_WALL_SECONDS` 双重保护，超限落 `failed`。

## 5. 工作流清单

| 名称 | 触发 | 行为 |
| --- | --- | --- |
| `web_fallback` | 显式/推断为联网检索，或资料无证据且 `WEB_SEARCH_REQUIRE_CONFIRMATION=true` | 先检索本地证据；无证据则登记 `web_search` 待确认动作，批准后联网回答 |
| `transcribe_to_minutes` | `POST /audio/{id}/confirm` 后异步触发 | 读取已确认转写 → 生成 **draft** 纪要；可选抽取行动项；绝不自动确认 |

> 自动纪要只创建 `draft`，用户仍需在纪要页编辑并确认，符合「候选与确认分离」。

## 6. 会话与消息

- 会话按 `user + scene + meeting` 唯一（`find_default_session`），
  `POST /agent/sessions/ensure` 幂等查找或创建。
- 每条用户消息先落库，再执行路由；助手消息在**成功 / 等待**时落库。
  失败不落助手消息：`agent_runs.error_code/error_message` 是唯一事实来源，
  同步路径抛 `502`、SSE 发 `event: error`，避免一次失败被渲染两遍。
- 多轮上下文：服务端按会话取最近 6 条 / ≤3000 字符的已完成消息注入 Prompt，
  排除当前这一轮与带 `pending_action_id` 的确认门提示；
  `AgentTurnOptions.include_history=false` 可关闭。
- `meta.pending_action_id` 把确认门挂到对应助手消息，刷新后仍可恢复。
- 思考过程（推理链）：问答类助手消息的 `meta` 还带 `reasoning`（原生推理文本，
  已截断）、`reasoning_ms`（思考耗时）与 `trace`（真实执行步骤数组），
  历史恢复后由前端折叠回看（`ai-design.md 3.12`）。
- 会话删除级联消息、运行、步骤与待确认动作。

## 7. 确认门（有副作用动作）

- 当前用于 `web_search`；后续可扩展转任务、发送通知等。
- `status`：`pending → approved | rejected | expired`，重复处理返回 `409`。
  置位由单条条件 UPDATE 完成（`agent_repository.claim_pending_action`），
  并发重复处理只有一个生效；数据库另有部分唯一索引
  `agent_pending_actions(run_id) WHERE status='pending'`
  （迁移 `0033_agent_pending_unique`）兜底，同一 run 只会有一张确认卡。
- 有效期由 `AGENT_PENDING_ACTION_TTL_MINUTES` 控制（默认 60 分钟）。
- 批准：工作流从暂停点继续，新增助手消息；沿用发起时的 `options`
  （模型 / 思考开关 / 模板），已有 `run_id` 且处于 `waiting` 时原地恢复，
  不新建 run。拒绝：运行 `cancelled`，追加「已取消」提示，不产生任何外部副作用。
- `WEB_SEARCH_ENABLED=false` 时批准会降级为拒答，不裸报错。

## 8. 持久化任务队列

- 表：`async_jobs`（新增 `attempts` / `max_attempts` / `next_run_at` /
  `locked_by` / `locked_at` / `heartbeat_at` / `priority` / `payload`）。
- 入队：`job_service.create_job(payload=...)`；`enqueue` 在
  `JOB_WORKER_ENABLED=true` 时只落库，不再注册 `BackgroundTasks`。
- 认领：PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`；SQLite/测试退化为
  单条条件更新。
- 重试：可重试错误回到 `pending` 并按 `attempts` 指数退避；超过
  `JOB_MAX_ATTEMPTS` 落 `failed`。
- 僵尸回收：worker 周期调用 `reap_stale`，依据 `heartbeat_at` / `started_at`
  与 `ASYNC_JOB_STALE_MINUTES`。
- 启动：`python -m app.worker`；Compose 服务名 `worker`。
- 回滚：`JOB_WORKER_ENABLED=false`，API 进程恢复用 `BackgroundTasks` 执行。

## 9. 前端集成

- `AgentChat.vue` 新增 `backendSession` / `agentScene` / `agentOptions`：
  - 挂载时 `ensureSession` → 加载历史与待确认动作；
  - 普通输入走 `POST /agent/turns/stream`，SSE 增量渲染；
  - 快捷任务（`onTask`）仍走页面既有专用链；
  - 确认门渲染为批准/拒绝卡片；
  - 加载失败或 404 自动回退 `storageKey` 的 localStorage 缓存。
- 思考过程（推理链）：`AgentChat` 的 `v-model:thinking`（默认开）写入
  `options.thinking`；`meta.trace`（真实执行步骤）与 `event: reasoning`
  （原生推理增量）驱动可折叠的 `AgentReasoningPanel`——生成中自动展开、
  正文首个增量后自动折叠、手动展开后保持、历史恢复默认折叠。
- 页面移除本地意图正则（`preparationIntent` / `minutesIntent` 等），
  改为监听 `@agent-result` 刷新准备稿、纪要、行动项。
- 开关：`VITE_AGENT_ENABLED`（默认开启）。

## 10. 快捷功能注册表与执行通道

### 10.1 注册表（单一事实来源）

前端 `frontend/src/config/quickActions.ts` 声明所有场景的快捷动作：

| 字段 | 作用 |
| --- | --- |
| `key` / `label` / `prompt` | 标识与展示文案；`prompt` 是后端实际收到的消息 |
| `scene` | `preprocess` / `asr` / `minutes`，与页面一一对应 |
| `intent` / `mode` | 显式意图与对话模式，跳过后端规则/LLM 路由 |
| `outputKind` | 前端渲染契约：`text` / `brief_card` / `summary_card` / `polish_diff` / `minutes` / `checklist` / `file` |
| `grounding` | `materials_only` / `materials_then_web` / `web_first` |
| `rationale` / `sourceUrls` / `lastReviewed` | 设计依据与复核时间，供季度评审逐条对照 |

- 注册表只引用动作与契约，**不复制工作流步骤**；步骤定义仍只在
  `backend/app/agent/workflows.py`。
- 前端契约测试 `frontend/tests/quickActions.spec.ts` 校验 key 唯一、
  intent/outputKind/grounding 合法、每个动作都有依据与复核时间。
- 当前只有 Web 端，注册表放前端即可；未来多端/后台可配置时再迁到
  `GET /agent/quick-actions`，字段保持不变。

### 10.2 两条执行通道

| 动作特征 | 通道 | 实现 |
| --- | --- | --- |
| 单次 LLM、无检索、无落库、无确认（润色/精简/改写/翻译） | `prompt` | `options.quick_task` → `ai_chat_service.quick_task` → `ai/prompts/quick.py` |
| 只读检索 + 生成 + 结构化校验（会前速览） | `pipeline` | `services/brief_service.py` → `ai/brief` → `MaterialBrief` |
| 有副作用 / 确认门 / 多步重试（纪要、待办、转写、联网） | `workflow` | `WorkflowRunner` + `agent/tools.py` |

判定规则：**“结构化输出”本身不构成 Workflow 理由**；只有出现
「有副作用 / 需要暂停确认 / ≥3 步且需重试」时才升级为 Workflow。

- `brief` 意图在规则层排在 `prepare` 之前，避免「摘要」被误判为准备稿；
- `brief` 只读**本场**资料（6 份 / 12000 字，单份 3000 字），不读历史资料，
  不产文件、不落库；
- `prepare` 的聊天回复只展示清单条数与前 3 条，完整准备稿在左侧确认卡查看。
- 页面接入方式：启用后端会话的页面（预处理/会后）由 `AgentChat` 透传
  `intent/mode/quick_task`；未启用后端会话的会中页由 `onQuickTask` 直接调用
  `POST /agent/turns`，避免 `quick_task` 退回普通对话。

### 10.3 Grounding 三级策略

| 级别 | 适用 | 行为 |
| --- | --- | --- |
| `materials_only`（默认） | 速览、清单、纪要、待办、转写 | 只读本场资料/记录；无证据就明说 |
| `materials_then_web` | 议程、发言要点、资料速查、待确认、会议检索 | 复用 `web_fallback`：本地无证据 → 确认门 → 联网 |
| `web_first` | 显式外部信息动作（当前未内置） | 直接联网，必须带引用 |

> “结合网上搜索”分两层：**产品调研**（一次性，注册表 `sourceUrls` 记录依据）
> 与**运行时联网**（按需，走确认门）。默认不给所有气泡开启运行时联网。

## 11. 可观测性与回滚

- `agent_runs` / `agent_run_steps` 记录工作流与每步尝试、输入输出摘要、错误码。
- `GET /agent/runs/{run_id}`、`GET /agent/runs/{run_id}/steps` 供排查。
- `POST /agent/runs/{run_id}/cancel` 标记取消；runner 在步骤间检查并停止。
- 回滚开关：`AGENT_ENABLED=false`、`WEB_SEARCH_REQUIRE_CONFIRMATION=false`、
  `JOB_WORKER_ENABLED=false`。

## 12. 测试

- `backend/tests/unit/test_agent_workflow.py`：条件边、重试、暂停、步数预算、意图路由。
- `backend/tests/api/test_agent.py`：会话复用、权限隔离、删除级联、确认门幂等、
  批准降级、开关 404。
- 前端 `AgentChatStream.spec.ts` / `AgentChat.spec.ts` 覆盖流式与持久化回退；
  `AgentChatBackend.spec.ts` 覆盖服务端历史恢复、确认门批准/拒绝与 404 回退。
