export interface UserMemory {
  role: string
  work_scenarios: string
  communication_style: string
  /** 内置枚举值（standard/concise/task_list）或模板清单中的模板 id */
  preferred_minutes_template: string | null
  updated_at: string | null
}

export interface UserMemoryPayload {
  role?: string
  work_scenarios?: string
  communication_style?: string
  preferred_minutes_template?: string | null
}
