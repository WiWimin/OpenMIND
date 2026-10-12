export type MinutesStatus = 'draft' | 'confirmed'

export interface Minutes {
  minutes_id: string
  meeting_id: string
  content: string
  status: MinutesStatus
  version: number
  source_record_ids: string[]
  created_at: string
  updated_at: string
}

export interface GenerateMinutesPayload {
  record_ids: string[]
  include_action_items?: boolean
}

export interface UpdateMinutesPayload {
  content?: string
}
