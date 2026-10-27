import http from '@/api/client'
import type { ApiSuccess } from '@/types/api'
import type { UserMemory, UserMemoryPayload } from '@/types/memory'
import { unwrapData } from '@/utils/apiEnvelope'

const PATH = '/me/memory'

export async function getMemory(): Promise<UserMemory> {
  const { data } = await http.get<ApiSuccess<UserMemory> | UserMemory>(PATH)
  return unwrapData(data)
}

export async function saveMemory(payload: UserMemoryPayload): Promise<UserMemory> {
  const { data } = await http.put<ApiSuccess<UserMemory> | UserMemory>(PATH, payload)
  return unwrapData(data)
}

export async function clearMemory(): Promise<{ deleted: boolean }> {
  const { data } = await http.delete<ApiSuccess<{ deleted: boolean }> | { deleted: boolean }>(
    PATH,
  )
  return unwrapData(data)
}
