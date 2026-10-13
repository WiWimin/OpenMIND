export type RecordType = 'manual' | 'transcript' | 'imported'

export interface MeetingRecord {
  record_id: string
  meeting_id: string
  content: string
  record_type: RecordType
  source_material_id: string | null
  created_at: string
  updated_at: string
}

export interface CreateRecordPayload {
  content: string
  record_type?: RecordType
}

export interface UpdateRecordPayload {
  content: string
}
