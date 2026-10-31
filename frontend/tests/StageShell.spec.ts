import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import StageShell from '@/components/StageShell.vue'
import type { Meeting } from '@/types/meeting'

const { pushMock, replaceMock, routeState } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
  routeState: {
    name: 'new-meeting-preprocess',
    fullPath: '/new-meeting/preprocess',
    query: {} as Record<string, string>,
    params: {},
    meta: {},
  },
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
  title: '项目启动会',
  topic: '里程碑与分工',
  meeting_time: '2026-10-18T10:00:00+08:00',
  status: 'scheduled',
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-10T09:00:00+08:00',
  archived_at: null,
}

function mountShell() {
  return mount(StageShell, {
    props: { stage: 'preprocess', title: '资料预处理' },
    slots: {
      default: '<p data-test="stage-slot">stage content</p>',
    },
    global: {
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('StageShell', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    routeState.query = {}
  })

  it('auto-selects the first scheduled meeting and renders the stage slot', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue({
      items: [meeting],
      pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
    })
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)

    const wrapper = mountShell()
    await flushPromises()

    expect(meetingsApi.getMeeting).toHaveBeenCalledWith('mtg_1')
    expect(replaceMock).toHaveBeenCalledWith({ query: { meetingId: 'mtg_1' } })
    expect(wrapper.find('[data-test="stage-slot"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('项目启动会')
  })

  it('shows the empty state when the user has no meetings', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue({
      items: [],
      pagination: { page: 1, page_size: 50, total: 0, total_pages: 1 },
    })

    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.text()).toContain('先选择一场会议')
    expect(wrapper.find('[data-test="stage-slot"]').exists()).toBe(false)
  })
})
