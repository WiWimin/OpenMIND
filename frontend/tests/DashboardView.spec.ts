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

const { pushMock, replaceMock, routeState } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
  routeState: { query: {} as Record<string, string | undefined> },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  useRoute: () => routeState,
}))

vi.mock('@/api/meetings', () => ({
  listMeetings: vi.fn(),
  createMeeting: vi.fn(),
  getMeeting: vi.fn(),
  updateMeeting: vi.fn(),
  deleteMeeting: vi.fn(),
  archiveMeeting: vi.fn(),
}))

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  updateTask: vi.fn(),
  cancelTask: vi.fn(),
}))

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

function listOf<T>(items: T[], total = items.length): ListData<T> {
  return { items, pagination: { page: 1, page_size: 20, total, total_pages: 1 } }
}

function mockMeetings(items: Meeting[], total = items.length) {
  vi.mocked(meetingsApi.listMeetings).mockImplementation(async (params = {}) => {
    if (params.status === 'scheduled') {
      const scheduled = items.filter((item) => item.status === 'scheduled')
      return listOf(scheduled, scheduled.length)
    }
    return listOf(items, total)
  })
}

function mockTasks(items: PersonalTask[], total = items.length) {
  vi.mocked(tasksApi.listTasks).mockImplementation(async (params = {}) => {
    if (params.status === 'todo') {
      const todo = items.filter((item) => item.status === 'todo')
      return listOf(todo, todo.length)
    }
    if (params.status === 'completed') {
      const completed = items.filter((item) => item.status === 'completed')
      return listOf(completed, completed.length)
    }
    return listOf(items, total)
  })
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
    routeState.query = {}
  })

  it('renders the merged hero, stats, meeting list and task list', async () => {
    mockMeetings([meeting], 5)
    mockTasks([task], 4)

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('OpenMIND')
    expect(wrapper.text()).toContain('智能会议记录、纪要生成与任务跟踪')

    const values = wrapper.findAll('.stat-card__value').map((node) => node.text())
    expect(values).toEqual(['5', '1', '1', '0'])

    expect(wrapper.text()).toContain('项目周会')
    expect(wrapper.text()).toContain('已安排 1 · 已归档 4')
    expect(wrapper.find('.meeting-card').exists()).toBe(true)

    expect(wrapper.find('#section-tasks').exists()).toBe(true)
    expect(wrapper.text()).toContain('整理周会议程')
    expect(wrapper.find('#task-status-filter').exists()).toBe(true)
  })

  it('shows the empty state when there are no meetings', async () => {
    mockMeetings([])
    mockTasks([])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有会议')
    expect(wrapper.find('.stat-card__value').text()).toBe('0')
  })

  it('opens the create dialog from the hero button and creates a meeting', async () => {
    mockMeetings([])
    mockTasks([])
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(meeting)

    const wrapper = mountView()
    await flushPromises()

    const heroCreate = wrapper
      .findAll('button')
      .find((button) => button.text() === '新建会议')
    await heroCreate?.trigger('click')
    expect(wrapper.find('.meeting-form').exists()).toBe(true)

    await wrapper.get('#meeting-title').setValue('项目周会')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(meetingsApi.createMeeting).toHaveBeenCalledWith({
      title: '项目周会',
      topic: undefined,
      meeting_time: undefined,
    })
    expect(wrapper.find('.meeting-form').exists()).toBe(false)
  })

  it('opens the create dialog when arriving with ?create=1', async () => {
    mockMeetings([])
    mockTasks([])
    routeState.query = { create: '1' }

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.meeting-form').exists()).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ query: {} })
  })

  it('navigates to the meeting detail when a card is clicked', async () => {
    mockMeetings([meeting])
    mockTasks([task])

    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.meeting-card').trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'meeting-detail',
      params: { meetingId: 'mtg_1' },
    })
  })

  it('filters the meeting list by status', async () => {
    mockMeetings([meeting], 5)
    mockTasks([task], 4)

    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#meeting-status-filter').setValue('archived')
    await flushPromises()

    expect(meetingsApi.listMeetings).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'archived' }),
    )
  })

  it('surfaces a list load error and retries', async () => {
    vi.mocked(meetingsApi.listMeetings)
      .mockRejectedValueOnce({ error_code: 'INTERNAL_ERROR', message: '服务异常' })
      .mockImplementation(async (params = {}) => {
        if (params.page_size === 1) {
          return { items: [], pagination: { page: 1, page_size: 1, total: 0, total_pages: 0 } }
        }
        return listOf([], 0)
      })
    mockTasks([])

    const wrapper = mountView()
    await flushPromises()

    const retryButton = wrapper.find('.error-message button')
    expect(retryButton.exists()).toBe(true)

    await retryButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('.meeting-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('还没有会议')
  })

  it('surfaces a stats load error and retries', async () => {
    mockMeetings([])
    vi.mocked(tasksApi.listTasks)
      .mockRejectedValueOnce({ error_code: 'INTERNAL_ERROR', message: '服务异常' })
      .mockResolvedValue(listOf([], 0))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('服务异常')

    const retryButtons = wrapper.findAll('.error-message button')
    await retryButtons[0]?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('服务异常')
  })

  it('appends more meetings through the load-more button', async () => {
    vi.mocked(meetingsApi.listMeetings).mockImplementation(async (params = {}) => {
      if (params.page_size === 1) {
        return listOf([], 0)
      }
      if (params.page === 2) {
        return {
          items: [{ ...meeting, meeting_id: 'mtg_2', title: '评审会' }],
          pagination: { page: 2, page_size: 20, total: 2, total_pages: 2 },
        }
      }
      return {
        items: [meeting],
        pagination: { page: 1, page_size: 20, total: 2, total_pages: 2 },
      }
    })
    mockTasks([])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('项目周会')
    const more = wrapper.findAll('button').find((item) => item.text() === '加载更多')
    expect(more).toBeDefined()

    await more?.trigger('click')
    await flushPromises()

    expect(meetingsApi.listMeetings).toHaveBeenLastCalledWith({ page: 2, page_size: 20 })
    expect(wrapper.text()).toContain('评审会')
  })
})
