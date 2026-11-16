// 与后端 schemas/issue.py 对齐（本地工作区双向同步）
// [待补] 同步契约的乐观锁/幂等字段还涉及以下文件，因不在本次修改范围，需后续补充：
// - types/record.ts：CreateRecordPayload 加 client_op_id?: string | null
// - types/record.ts：UpdateRecordPayload 加 expected_updated_at?: string
// - types/minutes.ts：UpdateMinutesPayload 加 expected_version?: number
// 注：若以上字段已在对应文件中补充，此备忘可删除。

export type IssueStatus = 'open' | 'resolved' | 'cancelled'

export interface IssueSource {
  record_id: string | null
}

export interface Issue {
  issue_id: string
  meeting_id: string
  description: string
  status: IssueStatus
  follow_up: string | null
  source: IssueSource
  created_at: string
  updated_at: string
}

export interface IssueCreatePayload {
  description: string
  follow_up?: string | null
  // 幂等键：同键重复提交返回已有实体
  client_op_id?: string | null
}

export interface IssueUpdatePayload {
  description?: string
  status?: IssueStatus
  follow_up?: string | null
  // 乐观锁：与服务端 updated_at 不一致时返回 409 SYNC_CONFLICT
  expected_updated_at?: string
}
