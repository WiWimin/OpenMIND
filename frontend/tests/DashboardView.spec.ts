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

// 首页同时拉取：统计数（page_size=1）与会议列表（page_size=20）
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
      return listOf(todo, total)
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

  it('renders the hero, intro card, meeting list and todo list', async () => {
    mockMeetings([meeting], 5)
    mockTasks([task], 4)

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('OpenMIND 智能会议助手')
    expect(wrapper.text()).toContain('基于 AI 的会议纪要、日程与任务协作平台')
    expect(wrapper.find('.home__summary').text()).toMatch(/今天有\s+1\s+场会议和\s+4\s+项待办任务/)
    expect(wrapper.find('img.home__mascot').exists()).toBe(true)

    const panels = wrapper.findAll('.home__panel')
    expect(panels).toHaveLength(2)
    expect(wrapper.text()).toContain('项目周会')
    expect(wrapper.findAll('.home__meeting')).toHaveLength(1)
    expect(wrapper.text()).toContain('整理周会议程')
    expect(wrapper.findAll('.home__task')).toHaveLength(1)
  })

  it('opens the create dialog from the intro CTA and creates a meeting', async () => {
    mockMeetings([meeting])
    mockTasks([task])
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(meeting)

    const wrapper = mountView()
    await flushPromises()

    const cta = wrapper.get('.home__cta')
    await cta.trigger('click')
    expect(wrapper.find('.meeting-form').exists()).toBe(true)

    await wrapper.get('#meeting-title').setValue('项目周会')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(meetingsApi.createMeeting).toHaveBeenCalledWith({
      title: '项目周会',
      topic: undefined,
      meeting_time: undefined,
    })
    expect(pushMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_1' },
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

  it('navigates to the meeting detail when a meeting row is clicked', async () => {
    mockMeetings([meeting])
    mockTasks([task])

    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.home__meeting').trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'meeting-detail',
      params: { meetingId: 'mtg_1' },
    })
  })

  it('shows the empty state when there are no meetings', async () => {
    mockMeetings([])
    mockTasks([])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有会议')
    expect(wrapper.text()).toContain('保持当前的会议节奏')
  })

  it('completes a task from the checklist', async () => {
    mockMeetings([meeting])
    mockTasks([task])
    vi.mocked(tasksApi.updateTask).mockResolvedValue({ ...task, status: 'completed' })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.home__task-check').setValue(true)
    await flushPromises()

    expect(tasksApi.updateTask).toHaveBeenCalledWith('tsk_1', { status: 'completed' })
    expect(wrapper.findAll('.home__task')).toHaveLength(0)
  })

  it('surfaces a meeting list error and retries', async () => {
    let listCalls = 0
    vi.mocked(meetingsApi.listMeetings).mockImplementation(async (params = {}) => {
      if (params.page_size === 1) {
        return { items: [], pagination: { page: 1, page_size: 1, total: 0, total_pages: 0 } }
      }
      listCalls += 1
      if (listCalls === 1) {
        throw { error_code: 'INTERNAL_ERROR', message: '服务异常' }
      }
      return listOf([], 0)
    })
    mockTasks([])

    const wrapper = mountView()
    await flushPromises()

    const retryButton = wrapper.get('.error-message button')
    await retryButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(false)
    expect(wrapper.text()).toContain('还没有会议')
  })

  it('surfaces a stats error and retries', async () => {
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
})
