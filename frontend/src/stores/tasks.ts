import { ref } from 'vue'
import { defineStore } from 'pinia'

import * as tasksApi from '@/api/tasks'
import { useAsyncList } from '@/composables/useAsyncList'
import type { PersonalTask, TaskStatus, UpdateTaskPayload } from '@/types/task'

export type TaskStatusFilter = TaskStatus | ''

export const useTasksStore = defineStore('tasks', () => {
  const filters = ref<{ status: TaskStatusFilter }>({ status: '' })

  const list = useAsyncList<PersonalTask>({
    fetcher: ({ page, page_size }) =>
      tasksApi.listTasks({
        page,
        page_size,
        status: filters.value.status || undefined,
      }),
  })

  function fetchList(page?: number): Promise<void> {
    return list.load(page)
  }

  function setPage(page: number): Promise<void> {
    return list.setPage(page)
  }

  function setStatusFilter(status: TaskStatusFilter): Promise<void> {
    filters.value.status = status
    return list.load(1)
  }

  function loadMore(): Promise<void> {
    return list.loadMore()
  }

  function sync(task: PersonalTask): void {
    const index = list.items.value.findIndex((item) => item.task_id === task.task_id)
    if (index !== -1) {
      list.items.value[index] = task
    }
  }

  async function updateTask(taskId: string, payload: UpdateTaskPayload): Promise<PersonalTask> {
    const task = await tasksApi.updateTask(taskId, payload)
    sync(task)
    return task
  }

  async function cancelTask(taskId: string): Promise<PersonalTask> {
    const task = await tasksApi.cancelTask(taskId)
    sync(task)
    return task
  }

  return {
    items: list.items,
    pagination: list.pagination,
    loading: list.loading,
    error: list.error,
    filters,
    fetchList,
    setPage,
    setStatusFilter,
    loadMore,
    updateTask,
    cancelTask,
  }
})
