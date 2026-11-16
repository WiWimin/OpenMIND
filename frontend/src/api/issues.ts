import http from '@/api/client'
import type { ApiSuccess, ListData } from '@/types/api'
import type { Issue, IssueCreatePayload, IssueUpdatePayload } from '@/types/issue'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

// 问题接口（本地工作区双向同步）：列表为标准分页信封（items + pagination）
export async function listIssues(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<Issue>> {
  const { data } = await http.get<ApiSuccess<ListData<Issue>> | ListData<Issue>>(
    `/meetings/${meetingId}/issues`,
    { params },
  )
  return unwrapData(data)
}

// 幂等创建：同 client_op_id 重复提交返回已有实体，同键不同内容返回 409 IDEMPOTENCY_KEY_REUSED
export async function createIssue(meetingId: string, payload: IssueCreatePayload): Promise<Issue> {
  const { data } = await http.post<ApiSuccess<Issue> | Issue>(
    `/meetings/${meetingId}/issues`,
    payload,
  )
  return unwrapData(data)
}

// 乐观锁：带 expected_updated_at 且不一致时返回 409 SYNC_CONFLICT
export async function updateIssue(issueId: string, payload: IssueUpdatePayload): Promise<Issue> {
  const { data } = await http.patch<ApiSuccess<Issue> | Issue>(`/issues/${issueId}`, payload)
  return unwrapData(data)
}
