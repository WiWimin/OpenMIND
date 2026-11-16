import http from '@/api/client'
import { extractJob, requireResourceId, waitForJob, type JobAccepted } from '@/api/jobs'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type { MeetingAudio } from '@/types/audio'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

async function fetchAudio(audioId: string): Promise<MeetingAudio> {
  const { data } = await http.get<ApiSuccess<MeetingAudio> | MeetingAudio>(`/audio/${audioId}`)
  return unwrapData(data)
}

/** 202 受理（api.md 1.9）→ 轮询终态 → 回查音频详情；同步契约保持原样 */
async function waitAudioJob(payload: MeetingAudio | JobAccepted): Promise<MeetingAudio> {
  const job = extractJob(payload)
  if (!job) {
    return payload as MeetingAudio
  }
  const finished = await waitForJob(job.job_id)
  return fetchAudio(requireResourceId(finished))
}

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

export async function uploadAudio(
  meetingId: string,
  file: File,
  clientOpId?: string | null,
): Promise<MeetingAudio> {
  const form = new FormData()
  form.append('file', file)
  if (clientOpId) {
    form.append('client_op_id', clientOpId)
  }
  const { data } = await http.post<
    ApiSuccess<MeetingAudio | JobAccepted> | MeetingAudio | JobAccepted
  >(`/meetings/${meetingId}/audio`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: LONG_REQUEST_TIMEOUT_MS,
  })
  return waitAudioJob(unwrapData<MeetingAudio | JobAccepted>(data))
}

export async function updateTranscript(audioId: string, transcript: string): Promise<MeetingAudio> {
  const { data } = await http.patch<ApiSuccess<MeetingAudio> | MeetingAudio>(`/audio/${audioId}`, {
    transcript,
  })
  return unwrapData(data)
}

export async function retryAudio(audioId: string): Promise<MeetingAudio> {
  const { data } = await http.post<
    ApiSuccess<MeetingAudio | JobAccepted> | MeetingAudio | JobAccepted
  >(`/audio/${audioId}/retry`, undefined, { timeout: LONG_REQUEST_TIMEOUT_MS })
  return waitAudioJob(unwrapData<MeetingAudio | JobAccepted>(data))
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

// 下载原始音频（非信封，Content-Disposition 携带文件名），用于本地工作区同步
export async function downloadAudio(audioId: string): Promise<Blob> {
  const { data } = await http.get<Blob>(`/audio/${audioId}/download`, {
    responseType: 'blob',
    timeout: LONG_REQUEST_TIMEOUT_MS,
  })
  return data
}

/* ============================ 实时录音：分片边录边转 ============================ */

export async function startLiveAudio(meetingId: string, fileType: string): Promise<MeetingAudio> {
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
