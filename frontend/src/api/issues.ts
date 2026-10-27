import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, ListData } from '@/types/api'
import type { ExtractIssuesPayload, OpenIssue, UpdateIssuePayload } from '@/types/issue'
import type { PageParams } from '@/types/pagination'
import { unwrapData, unwrapList } from '@/utils/apiEnvelope'

export async function extractIssues(
  meetingId: string,
  payload: ExtractIssuesPayload,
  signal?: AbortSignal,
): Promise<OpenIssue[]> {
  const { data } = await http.post<
    ApiSuccess<{ items: OpenIssue[] }> | { items: OpenIssue[] } | OpenIssue[]
  >(`/meetings/${meetingId}/issues/extract`, payload, {
    signal,
    timeout: LONG_REQUEST_TIMEOUT_MS,
  })
  return unwrapList<OpenIssue>(data)
}

export async function listIssues(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<OpenIssue>> {
  const { data } = await http.get<ApiSuccess<ListData<OpenIssue>> | ListData<OpenIssue>>(
    `/meetings/${meetingId}/issues`,
    { params },
  )
  return unwrapData(data)
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
