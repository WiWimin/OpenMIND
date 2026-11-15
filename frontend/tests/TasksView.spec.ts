import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as tasksApi from '@/api/tasks'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'
import TasksView from '@/views/TasksView.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
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
  priority: 'medium',
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

  it('renders the task list with status filter pills', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('我的任务')
    expect(wrapper.text()).toContain('整理周会议程')
    expect(wrapper.find('.task-section').exists()).toBe(true)

    // 状态筛选胶囊替代原统计卡片
    const pills = wrapper.findAll('.status-pill').map((node) => node.text())
    expect(pills).toEqual(['全部', '待处理', '进行中', '已完成'])
    expect(wrapper.findAll('.task-stat').length).toBe(0)
    expect(wrapper.find('.task-suggestion').exists()).toBe(false)
  })

  it('filters tasks by status pill', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    const completedPill = wrapper.findAll('.status-pill').find((node) => node.text() === '已完成')
    await completedPill?.trigger('click')
    await flushPromises()

    expect(tasksApi.listTasks).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      status: 'completed',
    })
    expect(wrapper.find('.status-pill--active').text()).toBe('已完成')
  })

  it('does not render the dashboard hero or meeting list', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.dashboard__hero').exists()).toBe(false)
    expect(wrapper.find('.stat-card').exists()).toBe(false)
    expect(wrapper.find('.task-suggestion').exists()).toBe(false)
    expect(wrapper.text()).toContain('还没有任务')
  })
})
