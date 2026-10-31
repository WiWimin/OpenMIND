// 与后端 schemas/chat.py 对齐
export type ChatContextScope = 'current_meeting' | 'current_and_history' | 'knowledge_base'

export interface ChatSource {
  meeting_id: string | null
  material_id: string | null
  record_id: string | null
  document_id?: string | null
  document_name?: string | null
  excerpt: string
}

export interface ChatPayload {
  question: string
  context_scope?: ChatContextScope
  include_sources?: boolean
  /** 可选：覆盖本次对话使用的模型名，须在模型配置中已登记 */
  model?: string
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
