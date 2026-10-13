export type MeetingStatus = 'scheduled' | 'archived'

export interface Meeting {
  meeting_id: string
  title: string
  topic: string | null
  meeting_time: string | null
  status: MeetingStatus
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
