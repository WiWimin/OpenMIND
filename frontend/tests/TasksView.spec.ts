import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as tasksApi from '@/api/tasks'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'
import TasksView from '@/views/TasksView.vue'

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
  title: '整理周会议程',
  status: 'todo',
  due_date: null,
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
}

function listOf<T>(items: T[]): ListData<T> {
  return { items, pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 } }
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(TasksView, { global: { plugins: [pinia] } })
}

describe('TasksView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders only the personal task section', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('我的任务')
    expect(wrapper.text()).toContain('整理周会议程')
    expect(wrapper.find('#task-status-filter').exists()).toBe(true)
    expect(wrapper.find('.task-section').exists()).toBe(true)
  })

  it('does not render the dashboard hero or meeting list', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.dashboard__hero').exists()).toBe(false)
    expect(wrapper.find('.meeting-card').exists()).toBe(false)
    expect(wrapper.find('.stat-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('还没有任务')
  })
})
