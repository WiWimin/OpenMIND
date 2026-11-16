export type MeetingStatus = 'scheduled' | 'archived'

export interface Meeting {
  meeting_id: string
  title: string
  topic: string | null
  meeting_time: string | null
  status: MeetingStatus
  /** 卡片统计（仅列表接口返回；其余接口为默认值） */
  has_minutes?: boolean
  material_count?: number
  record_count?: number
  audio_count?: number
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface CreateMeetingPayload {
  title: string
  topic?: string
  meeting_time?: string
}

export interface UpdateMeetingPayload {
  title?: string
  topic?: string
  meeting_time?: string
}
