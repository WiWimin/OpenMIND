export type ModelConfigSource = 'user' | 'global' | 'none'
export type ModelPurpose = 'preparation' | 'chat' | 'minutes' | 'extraction'

export interface ModelConfig {
  llm_api_base: string
  llm_model: string
  llm_api_key_masked: string
  llm_source: ModelConfigSource
  llm_purpose_models: Partial<Record<ModelPurpose, string>>
  embedding_api_base: string
  embedding_model: string
  embedding_api_key_masked: string
  embedding_source: ModelConfigSource
  embedding_dim: number
}

export interface PurposeModelsPayload {
  models: Partial<Record<ModelPurpose, string>>
}

// PUT 请求：字段可按提供方整体省略，省略即清空该提供方。
export interface ModelConfigPayload {
  llm_api_base?: string
  llm_api_key?: string
  llm_model?: string
  embedding_api_base?: string
  embedding_api_key?: string
  embedding_model?: string
}

export interface ModelConfigDeleteResult {
  deleted: boolean
}
