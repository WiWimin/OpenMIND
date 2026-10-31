import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess } from '@/types/api'
import type { ChatPayload, ChatResult, OrganizePayload, OrganizeResult } from '@/types/chat'
import { unwrapData } from '@/utils/apiEnvelope'

export async function askMeeting(
  meetingId: string,
  payload: ChatPayload,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const { data } = await http.post<ApiSuccess<ChatResult> | ChatResult>(
    `/meetings/${meetingId}/chat`,
    payload,
    { timeout: LONG_REQUEST_TIMEOUT_MS, ...(signal ? { signal } : {}) },
  )
  return unwrapData(data)
}

export async function organizeRecords(
  meetingId: string,
  payload: OrganizePayload,
): Promise<OrganizeResult> {
  const { data } = await http.post<ApiSuccess<OrganizeResult> | OrganizeResult>(
    `/meetings/${meetingId}/organize`,
    payload,
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  return unwrapData(data)
}
