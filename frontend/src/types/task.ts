export type TaskStatus = 'todo' | 'in_progress' | 'completed' | 'cancelled'

export type TaskPriority = 'high' | 'medium' | 'low'

export interface PersonalTask {
  task_id: string
  user_id: string
  meeting_id: string | null
  action_id: string | null
  title: string
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  /** 关联会议标题（仅列表接口返回，无关联会议为 null） */
  meeting_title?: string | null
  created_at: string
  updated_at: string
}

export interface UpdateTaskPayload {
  title?: string
  due_date?: string
  status?: TaskStatus
  priority?: TaskPriority
}

export interface CreateTaskPayload {
  title: string
  due_date?: string
  priority?: TaskPriority
}
