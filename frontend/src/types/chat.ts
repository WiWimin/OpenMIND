// 与后端 schemas/chat.py 对齐
export type ChatContextScope = 'current_meeting' | 'current_and_history' | 'knowledge_base'

/** 对话模式：plan（先规划讨论）/ build（直接生成执行），当前为会话级 UI 状态 */
export type ChatMode = 'plan' | 'build'

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
  /** 输入源三级回退：text > audio_id > record_ids（空 = 最近 20 条 ≤8000 字记录） */
  record_ids?: string[]
  task?: OrganizeTask
  style?: string
  text?: string
  /** 用户附加要求：随任务注入后端设计好的提示词（快捷任务标记 + 用户补充文字场景） */
  instruction?: string
  audio_id?: string
  /** 可选：覆盖本次任务使用的模型名 */
  model?: string
}

export type OrganizeTask = 'organize' | 'summary' | 'brief' | 'polish'

export interface SummaryStructured {
  conclusion: string[]
  key_discussions: { topic: string; points: string[] }[]
  action_items: {
    task: string
    assignee: string | null
    deadline: string | null
    priority: string
    source_quote: string | null
  }[]
  open_questions: string[]
}

export interface PolishSuggestion {
  location: string
  original: string
  suggested: string
  reason: string
  confidence: string
}

export type OrganizeStructured = SummaryStructured | PolishSuggestion[]

export interface OrganizeResult {
  task: OrganizeTask
  organized_content: string
  structured: OrganizeStructured | null
  source_record_ids: string[]
}
