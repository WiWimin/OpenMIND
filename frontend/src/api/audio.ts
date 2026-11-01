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

/* ============================ 实时录音：分片边录边转 ============================ */

export async function startLiveAudio(
  meetingId: string,
  fileType: string,
): Promise<MeetingAudio> {
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/meetings/${meetingId}/audio/live/start`,
    { file_type: fileType },
  )
  return unwrapData(data)
}

export async function uploadLiveChunk(
  audioId: string,
  seq: number,
  offsetSeconds: number,
  blob: Blob,
  fileType: string,
): Promise<MeetingAudio> {
  const form = new FormData()
  form.append('file', blob, `chunk-${String(seq).padStart(4, '0')}.${fileType}`)
  form.append('seq', String(seq))
  form.append('offset_seconds', String(offsetSeconds))
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}/live/chunk`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: LONG_REQUEST_TIMEOUT_MS,
    },
  )
  return unwrapData(data)
}

export async function finishLiveAudio(audioId: string): Promise<MeetingAudio> {
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}/live/finish`,
    undefined,
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  return unwrapData(data)
}

export async function retrySegment(audioId: string, seq: number): Promise<MeetingAudio> {
  const { data } = await http.post<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}/segments/${seq}/retry`,
    undefined,
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  return unwrapData(data)
}

export async function updateSegmentMarker(
  audioId: string,
  seq: number,
  markerType: string | null,
): Promise<MeetingAudio> {
  const { data } = await http.patch<ApiSuccess<MeetingAudio> | MeetingAudio>(
    `/audio/${audioId}/segments/marker`,
    { seq, marker_type: markerType },
  )
  return unwrapData(data)
}
