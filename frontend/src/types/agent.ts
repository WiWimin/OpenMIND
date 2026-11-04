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
