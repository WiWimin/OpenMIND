import http from '@/api/client'
import type { ApiSuccess, DeletedResult } from '@/types/api'
import type {
  ActionItem,
  ConvertToTaskPayload,
  ExtractActionItemsPayload,
  UpdateActionItemPayload,
} from '@/types/actionItem'
import type { PersonalTask } from '@/types/task'
import { unwrapData, unwrapList } from '@/utils/apiEnvelope'

export async function extractActionItems(
  meetingId: string,
  payload: ExtractActionItemsPayload,
): Promise<ActionItem[]> {
  const { data } = await http.post<
    ApiSuccess<{ items: ActionItem[] }> | { items: ActionItem[] } | ActionItem[]
  >(`/meetings/${meetingId}/action-items/extract`, payload)
  return unwrapList<ActionItem>(data)
}

// 契约未规定列表响应形状，unwrapList 兼容 items 数组或裸数组
export async function listActionItems(meetingId: string): Promise<ActionItem[]> {
  const { data } = await http.get<
    ApiSuccess<{ items: ActionItem[] }> | { items: ActionItem[] } | ActionItem[]
  >(`/meetings/${meetingId}/action-items`)
  return unwrapList<ActionItem>(data)
}

// [提案] 行动项详情/删除接口（api.md 6.1）
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
