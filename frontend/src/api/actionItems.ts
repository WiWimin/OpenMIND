import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type {
  ActionItem,
  ConvertToTaskPayload,
  ExtractActionItemsPayload,
  UpdateActionItemPayload,
} from '@/types/actionItem'
import type { PageParams } from '@/types/pagination'
import type { PersonalTask } from '@/types/task'
import { unwrapData, unwrapList } from '@/utils/apiEnvelope'

export async function extractActionItems(
  meetingId: string,
  payload: ExtractActionItemsPayload,
  signal?: AbortSignal,
): Promise<ActionItem[]> {
  const { data } = await http.post<
    ApiSuccess<{ items: ActionItem[] }> | { items: ActionItem[] } | ActionItem[]
  >(`/meetings/${meetingId}/action-items/extract`, payload, {
    signal,
    timeout: LONG_REQUEST_TIMEOUT_MS,
  })
  return unwrapList<ActionItem>(data)
}

export async function listActionItems(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<ActionItem>> {
  const { data } = await http.get<ApiSuccess<ListData<ActionItem>> | ListData<ActionItem>>(
    `/meetings/${meetingId}/action-items`,
    { params },
  )
  return unwrapData(data)
}

export async function getActionItem(actionId: string): Promise<ActionItem> {
  const { data } = await http.get<ApiSuccess<ActionItem> | ActionItem>(`/action-items/${actionId}`)
  return unwrapData(data)
}

export async function updateActionItem(
  actionId: string,
  payload: UpdateActionItemPayload,
): Promise<ActionItem> {
  const { data } = await http.patch<ApiSuccess<ActionItem> | ActionItem>(
    `/action-items/${actionId}`,
    payload,
  )
  return unwrapData(data)
}

export async function deleteActionItem(actionId: string): Promise<DeletedResult<'action_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'action_id'>> | DeletedResult<'action_id'>
  >(`/action-items/${actionId}`)
  return unwrapData(data)
}

export async function confirmActionItem(actionId: string): Promise<ActionItem> {
  const { data } = await http.post<ApiSuccess<ActionItem> | ActionItem>(
    `/action-items/${actionId}/confirm`,
  )
  return unwrapData(data)
}

export async function convertActionItemToTask(
  actionId: string,
  payload: ConvertToTaskPayload,
): Promise<PersonalTask> {
  const { data } = await http.post<ApiSuccess<PersonalTask> | PersonalTask>(
    `/action-items/${actionId}/convert-to-task`,
    payload,
  )
  return unwrapData(data)
}
