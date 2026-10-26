export type KnowledgeStatus = 'uploaded' | 'processing' | 'processed' | 'failed'

export interface KnowledgeDocument {
  document_id: string
  file_name: string
  type: string
  processing_status: KnowledgeStatus
  parse_error: string | null
  created_at: string
}

export interface KnowledgeSearchHit {
  document_id: string
  file_name: string
  excerpt: string
  score: number
}

export interface KnowledgeSearchPayload {
  query: string
  top_k?: number
  min_score?: number
}

export interface KnowledgeSearchResult {
  items: KnowledgeSearchHit[]
}
