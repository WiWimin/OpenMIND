// 字段以 api.md 5.1–5.5 示例为准，B 实现后可能微调（待确认）
export type PreparationStatus = 'generating' | 'draft' | 'confirmed' | 'failed'

export interface Preparation {
  preparation_id: string
  meeting_id: string
  summary: string
  checklist: string[]
  status: PreparationStatus
  version: number
  created_at: string
  updated_at: string
}

export interface GeneratePreparationPayload {
  include_history?: boolean
  user_goal?: string
  /** 可选：覆盖本次生成使用的模型名，须在模型配置中已登记 */
  model?: string
  /** 可选：套用输出模板（内置或本人自定义） */
  template_id?: string
}

export interface UpdatePreparationPayload {
  summary?: string
  checklist?: string[]
}
