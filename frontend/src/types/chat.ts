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
  /** 是否请求模型思考模式（推理链）；关闭后不展示思考过程 */
  thinking?: boolean
}

export interface ChatResult {
  answer: string
  sources: ChatSource[]
  insufficient_evidence: boolean
  /** Build 模式产出（plan 或无证据时为 null） */
  file?: ChatFile | null
  /** 模型原生推理（思考过程）；同步接口不返回 */
  reasoning?: string
}

/** 思考过程（推理链）的执行步骤状态 */
export type ChatTraceStatus = 'running' | 'done' | 'error'

/** 真实执行步骤：只描述服务端真实发生过的阶段，不伪造模型推理 */
export interface ChatTraceStage {
  id: string
  label: string
  status: ChatTraceStatus
  detail?: string
}

/** 问答 trace：执行步骤 + 该模型是否会返回原生推理 */
export interface ChatTrace {
  stages: ChatTraceStage[]
  native_reasoning?: boolean
}

/** SSE 流式问答首帧 meta（api.md 5.7a）：先于首个 delta 下发 */
export interface ChatStreamMeta {
  insufficient_evidence: boolean
  sources: ChatSource[]
  model: string | null
  /** 真实执行步骤（旧后端可能没有，前端需容错） */
  trace?: ChatTrace
}

/** SSE 流式问答 done 帧：完整回答与用量 */
export interface ChatStreamDone {
  answer: string
  usage: { input: number; output: number } | null
  latency_ms: number
  /** 完整原生推理（与 reasoning 增量一致，供增量丢失时兜底） */
  reasoning?: string
  reasoning_ms?: number
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

/** 会前速览结构化卡（与后端 `schemas/chat.py::MaterialBrief` 对齐） */
export interface MaterialBrief {
  headline: string
  key_points: string[]
  decisions_needed: string[]
  risks: string[]
  next_step: string
}

export type OrganizeStructured = SummaryStructured | PolishSuggestion[] | MaterialBrief

export interface OrganizeResult {
  task: OrganizeTask
  organized_content: string
  structured: OrganizeStructured | null
  source_record_ids: string[]
}
