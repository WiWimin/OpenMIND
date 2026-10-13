import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { cancelTask, getTask, listTasks, updateTask } from '@/api/tasks'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)

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

describe('tasks api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists tasks with pagination and status filters', async () => {
    const list: ListData<PersonalTask> = {
      items: [task],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listTasks({ page: 1, status: 'todo' })).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/tasks', { params: { page: 1, status: 'todo' } })
  })

  it('gets a task', async () => {
    get.mockResolvedValue(response({ status: 'success', data: task }))

    await expect(getTask('tsk_1')).resolves.toEqual(task)
    expect(get).toHaveBeenCalledWith('/tasks/tsk_1')
  })

  it('updates a task status', async () => {
    patch.mockResolvedValue(response({ ...task, status: 'completed' }))

    await expect(updateTask('tsk_1', { status: 'completed' })).resolves.toEqual({
      ...task,
      status: 'completed',
    })
    expect(patch).toHaveBeenCalledWith('/tasks/tsk_1', { status: 'completed' })
  })

  it('cancels a task', async () => {
    post.mockResolvedValue(response({ ...task, status: 'cancelled' }))

    await expect(cancelTask('tsk_1')).resolves.toEqual({ ...task, status: 'cancelled' })
    expect(post).toHaveBeenCalledWith('/tasks/tsk_1/cancel')
  })
})
