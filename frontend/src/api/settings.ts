import http from '@/api/client'
import type { ApiSuccess } from '@/types/api'
import type {
  ModelConfigDeleteResult,
  ModelConfigRead,
  ModelConfigWrite,
} from '@/types/modelConfig'
import { unwrapData } from '@/utils/apiEnvelope'

export async function getModelConfig(): Promise<ModelConfigRead> {
  const { data } = await http.get<ApiSuccess<ModelConfigRead> | ModelConfigRead>(
    '/me/settings/model',
  )
  return unwrapData(data)
}

export async function saveModelConfig(payload: ModelConfigWrite): Promise<ModelConfigRead> {
  const { data } = await http.put<ApiSuccess<ModelConfigRead> | ModelConfigRead>(
    '/me/settings/model',
    payload,
  )
  return unwrapData(data)
}

export async function clearModelConfig(): Promise<ModelConfigDeleteResult> {
  const { data } = await http.delete<
    ApiSuccess<ModelConfigDeleteResult> | ModelConfigDeleteResult
  >('/me/settings/model')
  return unwrapData(data)
}
