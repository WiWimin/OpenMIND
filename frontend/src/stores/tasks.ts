import { ref } from 'vue'
import { defineStore } from 'pinia'

import * as tasksApi from '@/api/tasks'
import { useAsyncList } from '@/composables/useAsyncList'
import type { CreateTaskPayload, PersonalTask, TaskStatus, UpdateTaskPayload } from '@/types/task'

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

  /** 当前筛选下命中：新建/撤回后用于判断是否就地插入或移出列表 */
  function matchesFilter(task: PersonalTask): boolean {
    return !filters.value.status || task.status === filters.value.status
  }

  async function createTask(payload: CreateTaskPayload): Promise<PersonalTask> {
    const task = await tasksApi.createTask(payload)
    if (matchesFilter(task)) {
      list.items.value = [task, ...list.items.value]
      list.pagination.value = { ...list.pagination.value, total: list.pagination.value.total + 1 }
    }
    return task
  }

  async function updateTask(taskId: string, payload: UpdateTaskPayload): Promise<PersonalTask> {
    const task = await tasksApi.updateTask(taskId, payload)
    sync(task)
    return task
  }

  /** 撤回：completed → todo（归档页「撤回到待办」） */
  async function revertTask(taskId: string): Promise<PersonalTask> {
    const task = await tasksApi.updateTask(taskId, { status: 'todo' })
    list.items.value = list.items.value.filter((item) => item.task_id !== taskId)
    list.pagination.value = { ...list.pagination.value, total: Math.max(list.pagination.value.total - 1, 0) }
    return task
  }

  async function cancelTask(taskId: string): Promise<PersonalTask> {
    const task = await tasksApi.cancelTask(taskId)
    if (matchesFilter(task)) {
      sync(task)
    } else {
      list.items.value = list.items.value.filter((item) => item.task_id !== taskId)
      list.pagination.value = { ...list.pagination.value, total: Math.max(list.pagination.value.total - 1, 0) }
    }
    return task
  }

  return {
    items: list.items,
    pagination: list.pagination,
    loading: list.loading,
    error: list.error,
    filters,
    fetchList,
    setStatusFilter,
    loadMore,
    createTask,
    updateTask,
    revertTask,
    cancelTask,
  }
})
