import http from '@/api/client'
import type { ApiSuccess } from '@/types/api'
import type {
  ModelConfig,
  ModelConfigDeleteResult,
  ModelConfigPayload,
} from '@/types/modelConfig'
import { unwrapData } from '@/utils/apiEnvelope'

const PATH = '/me/settings/model'

export async function getModelConfig(): Promise<ModelConfig> {
  const { data } = await http.get<ApiSuccess<ModelConfig> | ModelConfig>(PATH)
  return unwrapData(data)
}

export async function saveModelConfig(payload: ModelConfigPayload): Promise<ModelConfig> {
  const { data } = await http.put<ApiSuccess<ModelConfig> | ModelConfig>(PATH, payload)
  return unwrapData(data)
}

export async function clearModelConfig(): Promise<ModelConfigDeleteResult> {
  const { data } = await http.delete<
    ApiSuccess<ModelConfigDeleteResult> | ModelConfigDeleteResult
  >(PATH)
  return unwrapData(data)
}
