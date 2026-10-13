import http from '@/api/client'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type { PageParams } from '@/types/pagination'
import type { CreateRecordPayload, MeetingRecord, UpdateRecordPayload } from '@/types/record'
import { unwrapData } from '@/utils/apiEnvelope'

export async function listRecords(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<MeetingRecord>> {
  const { data } = await http.get<ApiSuccess<ListData<MeetingRecord>> | ListData<MeetingRecord>>(
    `/meetings/${meetingId}/records`,
    { params },
  )
  return unwrapData(data)
}

export async function createRecord(
  meetingId: string,
  payload: CreateRecordPayload,
): Promise<MeetingRecord> {
  const { data } = await http.post<ApiSuccess<MeetingRecord> | MeetingRecord>(
    `/meetings/${meetingId}/records`,
    payload,
  )
  return unwrapData(data)
}

export async function updateRecord(
  recordId: string,
  payload: UpdateRecordPayload,
): Promise<MeetingRecord> {
  const { data } = await http.patch<ApiSuccess<MeetingRecord> | MeetingRecord>(
    `/records/${recordId}`,
    payload,
  )
  return unwrapData(data)
}

// [提案] 删除记录接口（api.md 4.11）
export async function deleteRecord(recordId: string): Promise<DeletedResult<'record_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'record_id'>> | DeletedResult<'record_id'>
  >(`/records/${recordId}`)
  return unwrapData(data)
}
