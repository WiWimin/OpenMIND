// 详情/删除接口为 [提案]（api.md 6.1）；source 字段以提取示例为准（待确认）
export type ActionItemStatus =
  | 'pending_confirmation'
  | 'confirmed'
  | 'converted'
  | 'cancelled'

export interface ActionItemSource {
  record_id: string
  excerpt: string
}

export interface ActionItem {
  action_id: string
  meeting_id: string
  content: string
  assignee: string | null
  due_date: string | null
  status: ActionItemStatus
  source: ActionItemSource | null
  created_at: string
  updated_at: string
}

export interface ExtractActionItemsPayload {
  record_ids: string[]
}

export interface UpdateActionItemPayload {
  content?: string
  assignee?: string
  due_date?: string
}

export interface ConvertToTaskPayload {
  title: string
  due_date?: string
}
