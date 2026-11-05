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
  embedding_source: Exclude<ModelConfigSource, 'user'>
  embedding_dim: number
  /** 仅保存响应有意义：false 表示保存时 probe 遇限流，密钥有效但未完成调用验证 */
  llm_probe_verified?: boolean
}

export interface PurposeModelsPayload {
  models: Partial<Record<ModelPurpose, string>>
}

// PUT 请求：仅支持 LLM BYOK；向量模型由服务端统一配置，不支持用户自备。
export interface ModelConfigPayload {
  llm_api_base?: string
  llm_api_key?: string
  llm_model?: string
}

export interface ModelConfigDeleteResult {
  deleted: boolean
}

export interface ProviderModels {
  /** 当前已保存的默认模型名 */
  llm_model: string
  /** 服务商可用模型清单（OpenAI 兼容 GET /models，已排序） */
  models: string[]
}
