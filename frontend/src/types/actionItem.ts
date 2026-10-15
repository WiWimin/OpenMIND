// 与后端 schemas/action_item.py 对齐：source 恒存在，其字段可空
export type ActionItemStatus =
  | 'pending_confirmation'
  | 'confirmed'
  | 'converted'
  | 'cancelled'

export interface ActionItemSource {
  record_id: string | null
  excerpt: string | null
}

export interface ActionItem {
  action_id: string
  meeting_id: string
  content: string
  assignee: string | null
  due_date: string | null
  status: ActionItemStatus
  source: ActionItemSource
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
