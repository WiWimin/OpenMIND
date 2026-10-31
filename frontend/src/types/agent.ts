export interface AgentQuickAction {
  label: string
  prompt: string
}

export interface AgentSource {
  label: string
  detail?: string
}

export interface AgentReply {
  content: string
  sources?: AgentSource[]
  note?: string
}

export type AgentSendHandler = (text: string, signal: AbortSignal) => Promise<AgentReply | string>

export interface AgentChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  createdAt: number
  context?: string
  streaming: boolean
  sources?: AgentSource[]
  note?: string
  error?: boolean
  regenerateText?: string
}
