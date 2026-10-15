import http from '@/api/client'
import type { ApiSuccess, ListData } from '@/types/api'
import type { PageParams } from '@/types/pagination'
import type {
  GeneratePreparationPayload,
  Preparation,
  UpdatePreparationPayload,
} from '@/types/preparation'
import { unwrapData } from '@/utils/apiEnvelope'

export async function generatePreparation(
  meetingId: string,
  payload: GeneratePreparationPayload,
): Promise<Preparation> {
  const { data } = await http.post<ApiSuccess<Preparation> | Preparation>(
    `/meetings/${meetingId}/prepare`,
    payload,
  )
  return unwrapData(data)
}

export async function listPreparations(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<Preparation>> {
  const { data } = await http.get<ApiSuccess<ListData<Preparation>> | ListData<Preparation>>(
    `/meetings/${meetingId}/preparations`,
    { params },
  )
  return unwrapData(data)
}

export async function getPreparation(preparationId: string): Promise<Preparation> {
  const { data } = await http.get<ApiSuccess<Preparation> | Preparation>(
    `/preparations/${preparationId}`,
  )
  return unwrapData(data)
}

export async function updatePreparation(
  preparationId: string,
  payload: UpdatePreparationPayload,
): Promise<Preparation> {
  const { data } = await http.patch<ApiSuccess<Preparation> | Preparation>(
    `/preparations/${preparationId}`,
    payload,
  )
  return unwrapData(data)
}

export async function confirmPreparation(preparationId: string): Promise<Preparation> {
  const { data } = await http.post<ApiSuccess<Preparation> | Preparation>(
    `/preparations/${preparationId}/confirm`,
  )
  return unwrapData(data)
}
