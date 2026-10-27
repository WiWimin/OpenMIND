export type RecordType = 'manual' | 'transcript' | 'imported'
export type RecordMarkerType = 'highlight' | 'decision' | 'question'

export interface MeetingRecord {
  record_id: string
  meeting_id: string
  content: string
  record_type: RecordType
  marker_type: RecordMarkerType | null
  source_material_id: string | null
  created_at: string
  updated_at: string
}

export interface CreateRecordPayload {
  content: string
  record_type?: RecordType
  marker_type?: RecordMarkerType | null
}

export interface UpdateRecordPayload {
  content?: string
  marker_type?: RecordMarkerType | null
}
