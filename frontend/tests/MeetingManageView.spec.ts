import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as audioApi from '@/api/audio'
import * as meetingsApi from '@/api/meetings'
import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import * as recordsApi from '@/api/records'
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

vi.mock('@/api/materials', () => ({ listMaterials: vi.fn() }))
vi.mock('@/api/audio', () => ({ listAudio: vi.fn() }))
vi.mock('@/api/minutes', () => ({ listMinutes: vi.fn() }))
vi.mock('@/api/records', () => ({ listRecords: vi.fn() }))

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

function listOf<T>(items: T[], total = items.length) {
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
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([]))
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([]))
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([]))
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
  })

  it('renders category folders with uncategorized meetings hidden until entered', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('会议列表')
    const folderNames = wrapper.findAll('.folder-row__name').map((node) => node.text())
    expect(folderNames).toEqual(['未分类'])
    // 根视图不直接平铺会议行
    expect(wrapper.findAll('.meeting-row').length).toBe(0)
  })

  it('enters a folder on click and lists its meetings with a breadcrumb', async () => {
    const wrapper = mountView()
    await flushPromises()

    const folderButton = wrapper.findAll('.folder-row__expander')[0]
    await folderButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('未分类')
    const rows = wrapper.findAll('.meeting-row')
    expect(rows.length).toBe(2)
    expect(wrapper.find('.app-breadcrumb').exists()).toBe(true)
  })

  it('opens the meeting file list view from a meeting row', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('.folder-row__expander')[0].trigger('click')
    const nameButton = wrapper.findAll('.meeting-row__name')[0]
    await nameButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('项目启动会')
    expect(wrapper.text()).toContain('打开会议工作台')
    expect(wrapper.text()).toContain('会议资料')
    expect(wrapper.find('.meeting-files-panel').exists()).toBe(true)
  })

  it('navigates back to the folder list via the breadcrumb', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('.folder-row__expander')[0].trigger('click')
    await wrapper.findAll('.meeting-row__name')[0].trigger('click')
    await flushPromises()

    const backLink = wrapper
      .findAll('.app-breadcrumb__link')
      .find((node) => node.text() === '会议管理')
    await backLink?.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.folder-row').length).toBeGreaterThan(0)
    expect(wrapper.find('.meeting-files-panel').exists()).toBe(false)
  })

  it('filters meetings client-side by search keyword inside a folder', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('.folder-row__expander')[0].trigger('click')
    await wrapper.find('.search-box__input').setValue('需求')
    await flushPromises()

    const rows = wrapper.findAll('.meeting-row')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('需求评审会')
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
