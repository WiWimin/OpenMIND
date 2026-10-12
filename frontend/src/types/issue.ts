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
