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
  // 幂等键：同键重复提交返回已有实体（迁移 0026）
  client_op_id?: string | null
}

export interface UpdateRecordPayload {
  content?: string
  marker_type?: RecordMarkerType | null
  // 乐观锁：与服务端 updated_at 不一致时返回 409 SYNC_CONFLICT
  expected_updated_at?: string
}
