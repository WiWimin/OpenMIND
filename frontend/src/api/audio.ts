import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type { MeetingAudio } from '@/types/audio'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

export async function listAudio(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<MeetingAudio>> {
  const { data } = await http.get<ApiSuccess<ListData<MeetingAudio>> | ListData<MeetingAudio>>(
    `/meetings/${meetingId}/audio`,
    { params },
  )
  return unwrapData(data)
}

export async function uploadAudio(meetingId: string, file: File): Promise<MeetingAudio> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/meetings/${meetingId}/audio`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: LONG_REQUEST_TIMEOUT_MS,
    },
  )
  return unwrapData(data)
}

export async function updateTranscript(
  audioId: string,
  transcript: string,
): Promise<MeetingAudio> {
  const { data } = await http.patch<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}`,
    { transcript },
  )
  return unwrapData(data)
}

export async function retryAudio(audioId: string): Promise<MeetingAudio> {
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}/retry`,
    undefined,
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  return unwrapData(data)
}

export async function confirmAudio(audioId: string): Promise<MeetingAudio> {
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}/confirm`,
  )
  return unwrapData(data)
}

export async function deleteAudio(audioId: string): Promise<DeletedResult<'audio_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'audio_id'>> | DeletedResult<'audio_id'>
  >(`/audio/${audioId}`)
  return unwrapData(data)
}

export async function getAudio(audioId: string): Promise<MeetingAudio> {
  const { data } = await http.get<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}`,
  )
  return unwrapData(data)
}
