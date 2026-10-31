import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import type { Meeting } from '@/types/meeting'
import MeetingManageView from '@/views/meetings/MeetingManageView.vue'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('@/api/meetings', () => ({
  listMeetings: vi.fn(),
  createMeeting: vi.fn(),
  getMeeting: vi.fn(),
  updateMeeting: vi.fn(),
  deleteMeeting: vi.fn(),
  archiveMeeting: vi.fn(),
}))

const meetings: Meeting[] = [
  {
    meeting_id: 'mtg_1',
    title: '项目启动会',
    topic: '里程碑与分工',
    meeting_time: '2026-10-18T10:00:00+08:00',
    status: 'scheduled',
    created_at: '2026-10-01T09:00:00+08:00',
    updated_at: '2026-10-10T09:00:00+08:00',
    archived_at: null,
  },
  {
    meeting_id: 'mtg_2',
    title: '需求评审会',
    topic: null,
    meeting_time: null,
    status: 'archived',
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-10T09:00:00+08:00',
    archived_at: '2026-09-10T09:00:00+08:00',
  },
]

function listOf(items: Meeting[], total = items.length) {
  return {
    items,
    pagination: { page: 1, page_size: 100, total, total_pages: 1 },
  }
}

function mountView() {
  return mount(MeetingManageView)
}

describe('MeetingManageView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.localStorage.clear()
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf(meetings))
  })

  it('renders the meeting list as folders with status badges', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('会议列表')
    expect(wrapper.text()).toContain('项目启动会')
    expect(wrapper.text()).toContain('需求评审会')
    expect(wrapper.text()).toContain('已安排')
    expect(wrapper.text()).toContain('已归档')
    expect(wrapper.findAll('.meeting-row').length).toBe(2)
  })

  it('filters meetings by status', async () => {
    const wrapper = mountView()
    await flushPromises()

    const chip = wrapper.findAll('button').find((button) => button.text() === '已归档')
    await chip?.trigger('click')
    await flushPromises()

    expect(meetingsApi.listMeetings).toHaveBeenCalledWith({
      page: 1,
      page_size: 100,
      status: 'archived',
    })
  })

  it('filters meetings client-side by search keyword', async () => {
    const wrapper = mountView()
    await flushPromises()

    const input = wrapper.find('.search-box__input')
    await input.setValue('需求')

    const rows = wrapper.findAll('.meeting-row')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('需求评审会')
    expect(wrapper.text()).not.toContain('项目启动会')
  })

  it('creates a meeting and assigns the selected category', async () => {
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue({
      ...meetings[0],
      meeting_id: 'mtg_new',
      title: '第 1 次周会',
    })
    const wrapper = mountView()
    await flushPromises()

    const createButton = wrapper.findAll('button').find((button) => button.text() === '新建会议')
    await createButton?.trigger('click')
    expect(wrapper.findComponent({ name: 'MeetingFormDialog' }).exists()).toBe(true)
  })
})
