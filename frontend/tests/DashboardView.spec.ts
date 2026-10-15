import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import * as tasksApi from '@/api/tasks'
import type { ListData } from '@/types/api'
import type { Meeting } from '@/types/meeting'
import type { PersonalTask } from '@/types/task'
import { useAuthStore } from '@/stores/auth'
import DashboardView from '@/views/DashboardView.vue'

vi.mock('@/api/meetings', () => ({ listMeetings: vi.fn() }))
vi.mock('@/api/tasks', () => ({ listTasks: vi.fn() }))

const meeting: Meeting = {
  meeting_id: 'mtg_1',
  title: '项目周会',
  topic: '进度与风险',
  meeting_time: '2026-10-02T14:00:00+08:00',
  status: 'scheduled',
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
  archived_at: null,
}

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

function listOf<T>(items: T[], total: number): ListData<T> {
  return { items, pagination: { page: 1, page_size: 5, total, total_pages: 1 } }
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = {
    user_id: 'u1',
    name: 'Alice',
    created_at: '2026-10-01T00:00:00+08:00',
  }
  return mount(DashboardView, {
    global: {
      plugins: [pinia],
      stubs: { RouterLink: true },
      renderStubDefaultSlot: true,
    },
  })
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders aggregated stats, recent meetings and recent tasks', async () => {
    vi.mocked(meetingsApi.listMeetings).mockImplementation(async (params = {}) => {
      if (params.status === 'scheduled') return listOf([], 3)
      return listOf([meeting], 5)
    })
    vi.mocked(tasksApi.listTasks).mockImplementation(async (params = {}) => {
      if (params.status === 'todo') return listOf([], 2)
      if (params.status === 'in_progress') return listOf([], 1)
      if (params.status === 'completed') return listOf([], 1)
      return listOf([task], 4)
    })

    const wrapper = mountView()
    await flushPromises()

    const values = wrapper.findAll('.stat-card__value').map((node) => node.text())
    expect(values).toEqual(['5', '2', '1', '1'])
    expect(wrapper.text()).toContain('项目周会')
    expect(wrapper.text()).toContain('整理周会议程')
    expect(wrapper.text()).toContain('已安排 3 · 已归档 2')
  })

  it('shows guidance when there is no data yet', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([], 0))
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([], 0))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有会议')
    expect(wrapper.text()).toContain('还没有个人任务')
    expect(wrapper.find('.stat-card__value').text()).toBe('0')
  })

  it('surfaces a load error and retries', async () => {
    vi.mocked(meetingsApi.listMeetings)
      .mockRejectedValueOnce({ error_code: 'INTERNAL_ERROR', message: '服务异常' })
      .mockResolvedValue(listOf([], 0))
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([], 0))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(true)

    await wrapper.get('.error-message button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(false)
    expect(wrapper.get('.stat-card__value').text()).toBe('0')
  })
})
