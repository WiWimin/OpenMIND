import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as tasksApi from '@/api/tasks'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'
import { useTasksStore } from '@/stores/tasks'
import TaskArchiveView from '@/views/tasks/TaskArchiveView.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  updateTask: vi.fn(),
  cancelTask: vi.fn(),
}))

const task: PersonalTask = {
  task_id: 'tsk_1',
  user_id: 'u1',
  meeting_id: 'mtg_1',
  action_id: 'act_1',
  title: '完成上线检查清单',
  status: 'completed',
  due_date: '2026-10-20',
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-02T09:00:00+08:00',
}

function listOf<T>(items: T[]): ListData<T> {
  return { items, pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 } }
}

describe('TaskArchiveView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('loads completed tasks by default', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(TaskArchiveView, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(tasksApi.listTasks).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: 'completed',
    })
    expect(wrapper.text()).toContain('已完成 1 项')
    expect(wrapper.text()).toContain('完成上线检查清单')
    expect(useTasksStore().filters.status).toBe('completed')
  })
})
