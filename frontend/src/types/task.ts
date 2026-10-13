export type TaskStatus = 'todo' | 'in_progress' | 'completed' | 'cancelled'

export interface PersonalTask {
  task_id: string
  user_id: string
  meeting_id: string | null
  action_id: string | null
  title: string
  status: TaskStatus
  due_date: string | null
  created_at: string
  updated_at: string
}

export interface UpdateTaskPayload {
  title?: string
  due_date?: string
  status?: TaskStatus
}
