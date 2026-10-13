import http from '@/api/client'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type {
  CreateMeetingPayload,
  Meeting,
  MeetingStatus,
  UpdateMeetingPayload,
} from '@/types/meeting'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

export interface MeetingListParams extends PageParams {
  status?: MeetingStatus
}

export async function listMeetings(
  params: MeetingListParams = {},
): Promise<ListData<Meeting>> {
  const { data } = await http.get<ApiSuccess<ListData<Meeting>> | ListData<Meeting>>('/meetings', {
    params,
  })
  return unwrapData(data)
}

export async function createMeeting(payload: CreateMeetingPayload): Promise<Meeting> {
  const { data } = await http.post<ApiSuccess<Meeting> | Meeting>('/meetings', payload)
  return unwrapData(data)
}

export async function getMeeting(meetingId: string): Promise<Meeting> {
  const { data } = await http.get<ApiSuccess<Meeting> | Meeting>(`/meetings/${meetingId}`)
  return unwrapData(data)
}

export async function updateMeeting(
  meetingId: string,
  payload: UpdateMeetingPayload,
): Promise<Meeting> {
  const { data } = await http.patch<ApiSuccess<Meeting> | Meeting>(
    `/meetings/${meetingId}`,
    payload,
  )
  return unwrapData(data)
}

export async function deleteMeeting(meetingId: string): Promise<DeletedResult<'meeting_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'meeting_id'>> | DeletedResult<'meeting_id'>
  >(`/meetings/${meetingId}`)
  return unwrapData(data)
}

export async function archiveMeeting(meetingId: string): Promise<Meeting> {
  const { data } = await http.post<ApiSuccess<Meeting> | Meeting>(`/meetings/${meetingId}/archive`)
  return unwrapData(data)
}
