import type { ChatFile, OrganizeStructured } from './chat'

export interface AgentQuickAction {
  label: string
  prompt: string
  /** 快捷任务：走 onTask 专用实现链（后端 prompt 模块），而非普通对话 */
  task?: string
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
  /** 结构化回复：summary（要点卡片）/ polish（口误修改建议） */
  kind?: 'summary' | 'polish'
  structured?: OrganizeStructured
}

export type AgentSendHandler = (text: string, signal: AbortSignal) => Promise<AgentReply | string>

/** 流式发送的回调（SSE 首帧 meta 与正文增量），由 AgentChat 在 runTurn 内提供 */
export interface AgentStreamHandlers {
  /** 首帧 meta 到达：sources 已由视图映射为 AgentSource，先于正文渲染 */
  onMeta?: (sources: AgentSource[]) => void
  /** 正文增量：直接追加到当前 assistant 消息（不走打字动画） */
  onDelta?: (text: string) => void
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
  kind?: 'summary' | 'polish'
  structured?: OrganizeStructured
}
