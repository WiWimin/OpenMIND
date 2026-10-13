export type MaterialProcessingStatus = 'uploaded' | 'processing' | 'processed' | 'failed'

export interface Material {
  material_id: string
  meeting_id: string
  file_name: string
  type: string
  source: string | null
  processing_status: MaterialProcessingStatus
  parse_error: string | null
  created_at: string
}

export interface MaterialUploadPayload {
  file: File
  source?: string
  material_type?: string
}
