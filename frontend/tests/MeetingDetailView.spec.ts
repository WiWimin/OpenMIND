import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as issuesApi from '@/api/issues'
import * as meetingsApi from '@/api/meetings'
import * as materialsApi from '@/api/materials'
import type { Meeting } from '@/types/meeting'
import MeetingDetailView from '@/views/meetings/MeetingDetailView.vue'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ params: { meetingId: 'mtg_1' } }),
}))

vi.mock('@/api/meetings', () => ({
  listMeetings: vi.fn(),
  createMeeting: vi.fn(),
  getMeeting: vi.fn(),
  updateMeeting: vi.fn(),
  deleteMeeting: vi.fn(),
  archiveMeeting: vi.fn(),
}))

vi.mock('@/api/materials', () => ({
  listMaterials: vi.fn(),
  uploadMaterial: vi.fn(),
  getMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
}))

vi.mock('@/api/issues', () => ({
  extractIssues: vi.fn(),
  listIssues: vi.fn(),
  updateIssue: vi.fn(),
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

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(MeetingDetailView, { global: { plugins: [pinia] } })
}

function headerButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((button) => button.text() === text)
}

describe('MeetingDetailView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(materialsApi.listMaterials).mockResolvedValue({
      items: [],
      pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 },
    })
    vi.mocked(issuesApi.listIssues).mockResolvedValue({
      items: [],
      pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 },
    })
  })

  it('loads and renders the meeting with tab placeholders', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('项目周会')
    expect(wrapper.text()).toContain('进度与风险')
    expect(wrapper.findAll('[role="tab"]')).toHaveLength(6)
  })

  it('renders the material section on the materials tab', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.material-uploader').exists()).toBe(true)
  })

  it('renders the issues section on the issues tab', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    const wrapper = mountView()
    await flushPromises()

    const issuesTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text() === '问题')
    await issuesTab?.trigger('click')
    await flushPromises()

    expect(wrapper.find('.issues-section').exists()).toBe(true)
  })

  it('disables editing and archiving for an archived meeting', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue({ ...meeting, status: 'archived' })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('该会议已归档')
    expect(headerButton(wrapper, '编辑')?.attributes('disabled')).toBeDefined()
    expect(headerButton(wrapper, '归档')?.attributes('disabled')).toBeDefined()
  })

  it('archives the meeting after confirmation', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    vi.mocked(meetingsApi.archiveMeeting).mockResolvedValue({ ...meeting, status: 'archived' })
    const wrapper = mountView()
    await flushPromises()

    await headerButton(wrapper, '归档')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((button) => button.text() === '归档')
    await confirm?.trigger('click')
    await flushPromises()

    expect(meetingsApi.archiveMeeting).toHaveBeenCalledWith('mtg_1')
    expect(wrapper.text()).toContain('该会议已归档')
  })

  it('deletes the meeting and returns to the list', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    vi.mocked(meetingsApi.deleteMeeting).mockResolvedValue({ deleted: true, meeting_id: 'mtg_1' })
    const wrapper = mountView()
    await flushPromises()

    await headerButton(wrapper, '删除')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((button) => button.text() === '删除')
    await confirm?.trigger('click')
    await flushPromises()

    expect(meetingsApi.deleteMeeting).toHaveBeenCalledWith('mtg_1')
    expect(pushMock).toHaveBeenCalledWith({ name: 'meetings' })
  })
})
