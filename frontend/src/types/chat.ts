// 与后端 schemas/chat.py 对齐
export type ChatContextScope = 'current_meeting' | 'current_and_history' | 'knowledge_base'

/** 对话模式：plan（先规划讨论）/ build（直接生成执行），当前为会话级 UI 状态 */
export type ChatMode = 'plan' | 'build'

/** Build 模式产出的可交付文件（Markdown 正文；前端转 DOCX 下载/上传/镜像） */
export interface ChatFile {
  filename: string
  content: string
}

export interface ChatSource {
  meeting_id: string | null
  material_id: string | null
  record_id: string | null
  document_id?: string | null
  document_name?: string | null
  excerpt: string
  /** 来源类别：material（材料/知识库）| record（会议记录）| web（联网检索） */
  origin?: 'material' | 'record' | 'web'
  /** 联网来源的原始链接 */
  url?: string | null
  /** 联网来源的页面标题 */
  title?: string | null
}

export interface ChatPayload {
  question: string
  context_scope?: ChatContextScope
  include_sources?: boolean
  /** 可选：覆盖本次对话使用的模型名，须在模型配置中已登记 */
  model?: string
  /** 对话模式：plan=先讨论；build=产出可交付文件（缺省 plan） */
  mode?: ChatMode
}

export interface ChatResult {
  answer: string
  sources: ChatSource[]
  insufficient_evidence: boolean
  /** Build 模式产出（plan 或无证据时为 null） */
  file?: ChatFile | null
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
