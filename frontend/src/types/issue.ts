// 问题列表响应形状未在 api.md 规定，列表接口按数组处理（待确认）
export type IssueStatus = 'open' | 'resolved' | 'cancelled'

export interface OpenIssueSource {
  record_id: string
}

export interface OpenIssue {
  issue_id: string
  meeting_id: string
  description: string
  status: IssueStatus
  follow_up: string | null
  source: OpenIssueSource | null
  created_at: string
  updated_at: string
}

export interface ExtractIssuesPayload {
  record_ids: string[]
}

export interface UpdateIssuePayload {
  description?: string
  status?: IssueStatus
  follow_up?: string
}
