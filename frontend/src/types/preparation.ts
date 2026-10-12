export type PreparationStatus = 'generating' | 'draft' | 'confirmed' | 'failed'

export interface Preparation {
  preparation_id: string
  meeting_id: string
  summary: string
  checklist: string[]
  status: PreparationStatus
  version: number
  created_at: string
  updated_at: string
}

export interface GeneratePreparationPayload {
  include_history?: boolean
  user_goal?: string
}

export interface UpdatePreparationPayload {
  summary?: string
  checklist?: string[]
}
