import http from '@/api/client'
import type { ApiSuccess } from '@/types/api'
import type { ExtractIssuesPayload, OpenIssue, UpdateIssuePayload } from '@/types/issue'
import { unwrapData, unwrapList } from '@/utils/apiEnvelope'

export async function extractIssues(
  meetingId: string,
  payload: ExtractIssuesPayload,
): Promise<OpenIssue[]> {
  const { data } = await http.post<
    ApiSuccess<{ items: OpenIssue[] }> | { items: OpenIssue[] } | OpenIssue[]
  >(`/meetings/${meetingId}/issues/extract`, payload)
  return unwrapList<OpenIssue>(data)
}

// 契约未规定列表响应形状，unwrapList 兼容 items 数组或裸数组
export async function listIssues(meetingId: string): Promise<OpenIssue[]> {
  const { data } = await http.get<
    ApiSuccess<{ items: OpenIssue[] }> | { items: OpenIssue[] } | OpenIssue[]
  >(`/meetings/${meetingId}/issues`)
  return unwrapList<OpenIssue>(data)
}

export async function updateIssue(
  issueId: string,
  payload: UpdateIssuePayload,
): Promise<OpenIssue> {
  const { data } = await http.patch<ApiSuccess<OpenIssue> | OpenIssue>(
    `/issues/${issueId}`,
    payload,
  )
  return unwrapData(data)
}
