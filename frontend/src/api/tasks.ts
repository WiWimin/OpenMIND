import http from '@/api/client'
import type { ApiSuccess, ListData } from '@/types/api'
import type { PageParams } from '@/types/pagination'
import type { PersonalTask, TaskStatus, UpdateTaskPayload } from '@/types/task'
import { unwrapData } from '@/utils/apiEnvelope'

export interface TaskListParams extends PageParams {
  status?: TaskStatus
}

export async function listTasks(params: TaskListParams = {}): Promise<ListData<PersonalTask>> {
  const { data } = await http.get<ApiSuccess<ListData<PersonalTask>> | ListData<PersonalTask>>(
    '/tasks',
    { params },
  )
  return unwrapData(data)
}

export async function getTask(taskId: string): Promise<PersonalTask> {
  const { data } = await http.get<ApiSuccess<PersonalTask> | PersonalTask>(`/tasks/${taskId}`)
  return unwrapData(data)
}

export async function updateTask(
  taskId: string,
  payload: UpdateTaskPayload,
): Promise<PersonalTask> {
  const { data } = await http.patch<ApiSuccess<PersonalTask> | PersonalTask>(
    `/tasks/${taskId}`,
    payload,
  )
  return unwrapData(data)
}

export async function cancelTask(taskId: string): Promise<PersonalTask> {
  const { data } = await http.post<ApiSuccess<PersonalTask> | PersonalTask>(
    `/tasks/${taskId}/cancel`,
  )
  return unwrapData(data)
}
