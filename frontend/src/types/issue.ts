// 与后端 schemas/issue.py 对齐：source 恒存在，其字段可空
export type IssueStatus = 'open' | 'resolved' | 'cancelled'

export interface OpenIssueSource {
  record_id: string | null
}

export interface OpenIssue {
  issue_id: string
  meeting_id: string
  description: string
  status: IssueStatus
  follow_up: string | null
  source: OpenIssueSource
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
