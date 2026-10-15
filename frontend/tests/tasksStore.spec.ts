import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as tasksApi from '@/api/tasks'
import { useTasksStore } from '@/stores/tasks'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  updateTask: vi.fn(),
  cancelTask: vi.fn(),
}))

const task: PersonalTask = {
  task_id: 'tsk_1',
  user_id: 'usr_1',
  meeting_id: 'mtg_1',
  action_id: 'act_1',
  title: '完成接口联调',
  status: 'todo',
  due_date: null,
  created_at: '2026-10-01T10:10:00+08:00',
  updated_at: '2026-10-01T10:10:00+08:00',
}

function listOf(items: PersonalTask[]): ListData<PersonalTask> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

describe('tasks store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('loads tasks', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const store = useTasksStore()

    await store.fetchList()

    expect(store.items).toEqual([task])
    expect(tasksApi.listTasks).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: undefined,
    })
  })

  it('applies the status filter from page 1', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const store = useTasksStore()

    await store.setStatusFilter('completed')

    expect(store.filters.status).toBe('completed')
    expect(tasksApi.listTasks).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: 'completed',
    })
  })

  it('syncs an updated task into the list', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.updateTask).mockResolvedValue({ ...task, status: 'completed' })
    const store = useTasksStore()
    await store.fetchList()

    await store.updateTask('tsk_1', { status: 'completed' })

    expect(store.items[0].status).toBe('completed')
  })

  it('syncs a cancelled task into the list', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.cancelTask).mockResolvedValue({ ...task, status: 'cancelled' })
    const store = useTasksStore()
    await store.fetchList()

    await store.cancelTask('tsk_1')

    expect(store.items[0].status).toBe('cancelled')
  })
})
