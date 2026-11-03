import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import CreateMeetingView from '@/views/newMeeting/CreateMeetingView.vue'

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock, back: vi.fn() }),
}))

vi.mock('@/api/meetings', () => ({
  createMeeting: vi.fn(),
}))

const createDefaultMeetingFolder = vi.fn(async () => {})
const listSubdirs = vi.fn(async (): Promise<string[]> => [])

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({
    status: { value: 'unconfigured' },
    rootHandle: { value: null },
    directoryName: { value: '' },
    createDefaultMeetingFolder,
    listSubdirs,
  }),
}))

vi.mock('@/utils/localFileSystem', () => ({
  storeMeetingRoot: vi.fn(async () => {}),
  listSubdirs: (...args: unknown[]) => listSubdirs(...(args as [])),
  isLocalWorkspaceSupported: () => true,
}))

const created = {
  meeting_id: 'mtg_new',
  title: '项目周会',
  topic: null,
  meeting_time: null,
  status: 'scheduled' as const,
  created_at: '2026-11-04T09:00:00+08:00',
  updated_at: '2026-11-04T09:00:00+08:00',
  archived_at: null,
}

function mountView() {
  return mount(CreateMeetingView)
}

describe('CreateMeetingView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('creates a meeting, uses the default folder and enters the flow page', async () => {
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(created)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#meeting-title').setValue('  项目周会  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(meetingsApi.createMeeting).toHaveBeenCalledWith({
      title: '项目周会',
      topic: undefined,
      meeting_time: undefined,
    })
    // 未选择存储位置 → 已连接时落默认 <会议名>/；未连接时静默跳过
    expect(createDefaultMeetingFolder).toHaveBeenCalledWith('项目周会')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('requires a title before submitting', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入会议标题')
    expect(meetingsApi.createMeeting).not.toHaveBeenCalled()
  })

  it('shows the storage picker only when the workspace is connected', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).not.toContain('本地存储位置')
  })
})
