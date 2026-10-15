import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import type { ListData } from '@/types/api'
import type { Meeting } from '@/types/meeting'
import MeetingListView from '@/views/meetings/MeetingListView.vue'

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

function listOf(items: Meeting[]): ListData<Meeting> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(MeetingListView, { global: { plugins: [pinia] } })
}

describe('MeetingListView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    routeState.query = {}
  })

  it('shows the empty state when there are no meetings', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有会议')
  })

  it('renders the meeting list', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('项目周会')
  })

  it('navigates to the meeting detail when a card is clicked', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('.meeting-card').trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'meeting-detail',
      params: { meetingId: 'mtg_1' },
    })
  })

  it('creates a meeting from the dialog', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([]))
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(meeting)
    const wrapper = mountView()
    await flushPromises()

    const createButton = wrapper.findAll('button').find((button) => button.text() === '新建会议')
    await createButton?.trigger('click')
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
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([]))
    routeState.query = { create: '1' }
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.meeting-form').exists()).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ query: {} })
  })

  it('shows an error state and retries on demand', async () => {
    vi.mocked(meetingsApi.listMeetings)
      .mockRejectedValueOnce({ error_code: 'INTERNAL_ERROR', message: '服务异常' })
      .mockResolvedValue(listOf([meeting]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('服务异常')

    await wrapper.get('.error-message button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('项目周会')
  })
})
