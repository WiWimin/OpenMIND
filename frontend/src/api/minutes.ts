import http from '@/api/client'
import type { ApiSuccess, ListData } from '@/types/api'
import type { GenerateMinutesPayload, Minutes, UpdateMinutesPayload } from '@/types/minutes'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

export async function generateMinutes(
  meetingId: string,
  payload: GenerateMinutesPayload,
): Promise<Minutes> {
  const { data } = await http.post<ApiSuccess<Minutes> | Minutes>(
    `/meetings/${meetingId}/minutes/generate`,
    payload,
  )
  return unwrapData(data)
}

// [提案] 纪要读取/编辑/确认接口（api.md 5.11–5.14），待团队确认
export async function listMinutes(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<Minutes>> {
  const { data } = await http.get<ApiSuccess<ListData<Minutes>> | ListData<Minutes>>(
    `/meetings/${meetingId}/minutes`,
    { params },
  )
  return unwrapData(data)
}

export async function getMinutes(minutesId: string): Promise<Minutes> {
  const { data } = await http.get<ApiSuccess<Minutes> | Minutes>(`/minutes/${minutesId}`)
  return unwrapData(data)
}

export async function updateMinutes(
  minutesId: string,
  payload: UpdateMinutesPayload,
): Promise<Minutes> {
  const { data } = await http.patch<ApiSuccess<Minutes> | Minutes>(
    `/minutes/${minutesId}`,
    payload,
  )
  return unwrapData(data)
}

export async function confirmMinutes(minutesId: string): Promise<Minutes> {
  const { data } = await http.post<ApiSuccess<Minutes> | Minutes>(`/minutes/${minutesId}/confirm`)
  return unwrapData(data)
}
