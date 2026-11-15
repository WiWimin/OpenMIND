import type {
  ChatFile,
  ChatSource,
  ChatTrace,
  ChatTraceStage,
  OrganizeStructured,
} from './chat'

export type { ChatTrace, ChatTraceStage, ChatTraceStatus } from './chat'

export type QuickTask = 'polish' | 'condense' | 'rewrite' | 'translate'

export interface AgentQuickAction {
  label: string
  prompt: string
  /** 快捷任务：走 onTask 专用实现链（后端 prompt 模块），而非普通对话 */
  task?: string
  /** 显式意图：跳过后端规则/LLM 路由（快捷功能注册表使用） */
  intent?: AgentIntentName
  /** 对话模式：plan=先讨论；build=产出可交付文件 */
  mode?: 'plan' | 'build'
  /** 简单文本任务：走公共 prompt_task 通道（单次 LLM、无落库） */
  quickTask?: QuickTask
}

export interface AgentSource {
  label: string
  detail?: string
}

export interface AgentReply {
  content: string
  sources?: AgentSource[]
  note?: string
  /** Build 模式产出的可交付文件 */
  file?: ChatFile
  /**
   * 结构化回复：summary（要点卡片）/ brief（会前速览）/ polish（口误修改建议）
   * / minutes（纪要文件卡元数据）/ action_items（行动项清单卡）
   */
  kind?: 'summary' | 'brief' | 'polish' | 'minutes' | 'action_items'
  structured?: OrganizeStructured | MinutesDocMeta | AgentActionItemLite[]
  /** 模型原生推理（思考过程）；流式增量丢失时由 done 兜底 */
  reasoning?: string
  /** 思考耗时（毫秒） */
  reasoningMs?: number
  /** 真实执行步骤（理解 → 检索 → 生成） */
  trace?: ChatTraceStage[]
}

/** 会后产出：纪要文件卡的元数据（与后端 `AgentReply.structured` 对齐） */
export interface MinutesDocMeta {
  minutes_id: string
  version: number
  status: string
  template: string
  title: string
}

/** 会后产出：清单卡展示所需的行动项字段（与后端 `ActionItemRead` 对齐的子集） */
export interface AgentActionItemLite {
  action_id?: string
  content: string
  assignee?: string | null
  due_date?: string | null
  status?: string | null
  source?: { record_id?: string | null; excerpt?: string | null } | null
}

/** 点击文件卡/清单卡时向页面发出的打开请求 */
export interface AgentDocOpenEvent {
  kind: 'minutes' | 'action_items'
  meta?: MinutesDocMeta
}

export type AgentSendHandler = (text: string, signal: AbortSignal) => Promise<AgentReply | string>

/** 流式发送的回调（SSE 首帧 meta 与正文增量），由 AgentChat 在 runTurn 内提供 */
export interface AgentStreamHandlers {
  /** 首帧 meta 到达：sources 已由视图映射为 AgentSource，先于正文渲染 */
  onMeta?: (sources: AgentSource[], trace?: ChatTrace) => void
  /** 正文增量：直接追加到当前 assistant 消息（不走打字动画） */
  onDelta?: (text: string) => void
  /** 模型原生推理增量（思考过程） */
  onReasoning?: (text: string) => void
  /** 本轮是否请求模型思考模式（页面透传给后端） */
  thinking?: boolean
}

/**
 * 流式发送处理器（可选）：提供时普通对话（非快捷任务）走 SSE 增量渲染；
 * 返回的 AgentReply 用于补充 note/file/sources，未产生增量时 content 生效。
 */
export type AgentSendStreamHandler = (
  text: string,
  signal: AbortSignal,
  handlers: AgentStreamHandlers,
) => Promise<AgentReply | void>

/** 快捷任务处理器：task 对应后端 organize 链的任务类型 */
export type AgentTaskHandler = (
  task: string,
  prompt: string,
  signal: AbortSignal,
) => Promise<AgentReply | string>

/** 简单文本任务处理器：对应后端 `options.quick_task` 通道 */
export type AgentQuickTaskHandler = (
  task: QuickTask,
  text: string,
  signal: AbortSignal,
) => Promise<AgentReply | string>

export interface AgentChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  createdAt: number
  context?: string
  streaming: boolean
  sources?: AgentSource[]
  note?: string
  file?: ChatFile
  error?: boolean
  regenerateText?: string
  task?: string
  intent?: AgentIntentName
  mode?: 'plan' | 'build'
  quickTask?: QuickTask
  kind?: 'summary' | 'brief' | 'polish' | 'minutes' | 'action_items' | string
  structured?: OrganizeStructured | MinutesDocMeta | AgentActionItemLite[]
  /** 用户手动停止生成（正文保留，用状态行提示已停止） */
  stopped?: boolean
  /** 需要显示状态行的局部提示（如确认门失败），普通回复不显示 */
  statusNote?: boolean
  /** 服务端确认门：挂在该条助手消息下的待确认动作 */
  pendingAction?: AgentPendingAction
  /** 确认门处理中（禁用按钮） */
  pendingDeciding?: boolean
  /* ---------- 思考过程（推理链） ---------- */
  /** 模型原生推理文本 */
  reasoning?: string
  /** 思考是否已结束（用于「已思考 X 秒」与兜底提示） */
  reasoningDone?: boolean
  /** 思考耗时（毫秒） */
  reasoningDurationMs?: number
  /** 思考面板展开状态 */
  reasoningOpen?: boolean
  /** 用户手动展开过：正文开始后不再自动折叠 */
  reasoningPinned?: boolean
  /** 思考开始时间戳（用于计算耗时） */
  reasoningStartedAt?: number
  /** 服务端下发的真实执行步骤 */
  trace?: ChatTraceStage[]
  /** 该模型是否会返回原生推理（旧后端可能没有） */
  nativeReasoning?: boolean
}

/* ------------------------------------------------------------------ 后端会话 */

export type AgentScene = 'preprocess' | 'asr' | 'minutes'

export type AgentIntentName =
  | 'chat'
  | 'brief'
  | 'prepare'
  | 'organize'
  | 'minutes_generate'
  | 'action_items_extract'
  | 'issues_extract'
  | 'knowledge_search'
  | 'build_file'
  | 'web_search'
  | 'transcribe'
  | 'clarify'
  | 'help'

export interface AgentIntentDecision {
  intent: AgentIntentName
  confidence: number
  slots: Record<string, string>
  needs_clarification: boolean
  clarification_question: string | null
  source: 'explicit' | 'rule' | 'llm' | 'fallback'
}

export interface AgentTurnOptions {
  model?: string
  mode?: 'plan' | 'build'
  quick_task?: QuickTask
  template?: string
  template_id?: string
  context_scope?: string
  include_sources?: boolean
  include_history?: boolean
  include_action_items?: boolean
  include_materials?: boolean
  user_goal?: string
  context?: string
  /** 是否请求模型思考模式（推理链）；关闭后不下发 reasoning 事件 */
  thinking?: boolean
}

export interface AgentTurnPayload {
  session_id?: string
  meeting_id?: string
  scene?: AgentScene
  message: string
  intent?: AgentIntentName
  options?: AgentTurnOptions
}

export interface AgentBackendSession {
  session_id: string
  user_id: string
  meeting_id?: string | null
  scene: string
  title?: string | null
  status: string
  meta?: Record<string, unknown> | null
  created_at: string
  updated_at: string
  last_message_at?: string | null
}

export interface AgentBackendMessage {
  message_id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  kind?: string | null
  structured?: unknown | null
  sources?: ChatSource[] | null
  file?: ChatFile | null
  status: string
  job_id?: string | null
  meta?: Record<string, unknown> | null
  created_at: string
}

export interface AgentPendingAction {
  action_id: string
  session_id: string
  run_id?: string | null
  action_type: string
  question: string
  payload?: Record<string, unknown> | null
  status: 'pending' | 'approved' | 'rejected' | 'expired' | string
  expires_at?: string | null
  created_at: string
  decided_at?: string | null
}

export interface AgentRun {
  run_id: string
  session_id: string
  user_id: string
  meeting_id?: string | null
  workflow: string
  status: string
  current_step?: string | null
  state?: Record<string, unknown> | null
  job_id?: string | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface AgentTurnReply {
  content: string
  kind?: string | null
  structured?: unknown | null
  sources: ChatSource[]
  note?: string | null
  file?: ChatFile | null
  /** 意图对应的业务结果（准备稿/纪要/行动项），供页面刷新局部状态 */
  result?: unknown
  /** 模型原生推理（思考过程） */
  reasoning?: string | null
  reasoning_ms?: number | null
  /** 真实执行步骤 */
  trace?: ChatTraceStage[] | null
}

export interface AgentTurnResponse {
  session_id: string
  intent: AgentIntentDecision
  user_message?: AgentBackendMessage | null
  assistant_message?: AgentBackendMessage | null
  pending_action?: AgentPendingAction | null
  run?: AgentRun | null
  accepted: boolean
}

export interface AgentStreamDone {
  session_id: string
  intent: AgentIntentDecision
  message_id?: string | null
  reply: AgentTurnReply
}

/** Agent SSE 事件回调：intent → meta → reasoning、delta、pending_action/run → done */
export interface AgentBackendStreamHandlers {
  onIntent?: (intent: AgentIntentDecision) => void
  onMeta?: (meta: { sources: ChatSource[]; trace?: ChatTrace }) => void
  onDelta?: (text: string) => void
  /** 模型原生推理增量（思考过程） */
  onReasoning?: (text: string) => void
  onPendingAction?: (action: AgentPendingAction) => void
  onRun?: (run: AgentRun) => void
  onDone?: (done: AgentStreamDone) => void
  signal?: AbortSignal
}

/** 页面收到 Agent 业务结果时的刷新载荷 */
export interface AgentResultEvent {
  sessionId: string
  intent: AgentIntentDecision
  result?: unknown
}
