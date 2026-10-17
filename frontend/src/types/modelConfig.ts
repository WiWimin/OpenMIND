export interface ModelConfigRead {
  llm_api_base: string
  llm_model: string
  llm_api_key_masked: string
  embedding_api_base: string
  embedding_model: string
  embedding_api_key_masked: string
  embedding_dim: number
}

export interface ModelConfigWrite {
  llm_api_base?: string | null
  llm_api_key?: string | null
  llm_model?: string | null
  embedding_api_base?: string | null
  embedding_api_key?: string | null
  embedding_model?: string | null
}

export interface ModelConfigDeleteResult {
  deleted: boolean
}
