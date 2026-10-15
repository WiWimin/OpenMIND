// 与后端 schemas/chat.py 对齐
export type ChatContextScope = 'current_meeting' | 'current_and_history'

export interface ChatSource {
  meeting_id: string
  material_id: string
  record_id: string | null
  excerpt: string
}

export interface ChatPayload {
  question: string
  context_scope?: ChatContextScope
  include_sources?: boolean
}

export interface ChatResult {
  answer: string
  sources: ChatSource[]
  insufficient_evidence: boolean
}

export interface OrganizePayload {
  record_ids: string[]
  style?: string
}

export interface OrganizeResult {
  organized_content: string
  source_record_ids: string[]
}
