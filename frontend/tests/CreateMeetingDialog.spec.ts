import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import CreateMeetingDialog from '@/components/CreateMeetingDialog.vue'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/api/meetings', () => ({
  createMeeting: vi.fn(),
}))

const created = {
  meeting_id: 'mtg_new',
  title: '项目周会',
  topic: null,
  meeting_time: null,
  status: 'scheduled' as const,
  created_at: '2026-11-05T09:00:00+08:00',
  updated_at: '2026-11-05T09:00:00+08:00',
  archived_at: null,
}

const CATEGORIES_KEY = 'openmind.meeting.categories'
const MAP_KEY = 'openmind.meeting.categoryMap'

function readCategories(): Array<{ id: string; name: string }> {
  return JSON.parse(localStorage.getItem(CATEGORIES_KEY) ?? '[]') as Array<{
    id: string
    name: string
  }>
}

function readMap(): Record<string, string> {
  return JSON.parse(localStorage.getItem(MAP_KEY) ?? '{}') as Record<string, string>
}

/** 打开创建窗口（defineExpose 暴露的方法在 VTU 类型推断下需显式转型） */
function openWindow(wrapper: VueWrapper): void {
  ;(wrapper.vm as unknown as { open: () => void }).open()
}

async function openAndSubmit(wrapper: VueWrapper, title: string): Promise<void> {
  openWindow(wrapper)
  await flushPromises()

  await wrapper.get('#meeting-title').setValue(title)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('CreateMeetingDialog', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.localStorage.clear()
    pushMock.mockClear()
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(created)
  })

  it('creates a folder named after the meeting when no folder is chosen', async () => {
    const wrapper = mount(CreateMeetingDialog)
    await openAndSubmit(wrapper, '  项目周会  ')

    expect(meetingsApi.createMeeting).toHaveBeenCalledWith({
      title: '项目周会',
      topic: undefined,
      meeting_time: undefined,
    })

    const categories = readCategories()
    expect(categories.map((item) => item.name)).toContain('项目周会')
    expect(readMap().mtg_new).toBe(categories.find((item) => item.name === '项目周会')?.id)

    // 创建成功 → 进入三个功能卡片页
    expect(pushMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('reuses an existing folder with the same name instead of duplicating it', async () => {
    localStorage.setItem(
      CATEGORIES_KEY,
      JSON.stringify([{ id: 'cat_existing', name: '项目周会', createdAt: '2026-11-01' }]),
    )

    const wrapper = mount(CreateMeetingDialog)
    await openAndSubmit(wrapper, '项目周会')

    expect(readCategories()).toHaveLength(1)
    expect(readMap().mtg_new).toBe('cat_existing')
  })

  it('assigns the chosen folder and does not create a new one', async () => {
    localStorage.setItem(
      CATEGORIES_KEY,
      JSON.stringify([{ id: 'cat_weekly', name: '周会', createdAt: '2026-11-01' }]),
    )

    const wrapper = mount(CreateMeetingDialog)
    openWindow(wrapper)
    await flushPromises()

    await wrapper.get('#meeting-title').setValue('项目周会')
    await wrapper.get('#meeting-folder').setValue('cat_weekly')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(readCategories().map((item) => item.name)).toEqual(['周会'])
    expect(readMap().mtg_new).toBe('cat_weekly')
    expect(pushMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('shows the create window with the mascot decoration', async () => {
    const wrapper = mount(CreateMeetingDialog)
    expect(wrapper.find('.meeting-form').exists()).toBe(false)

    openWindow(wrapper)
    await flushPromises()

    expect(wrapper.find('.meeting-form').exists()).toBe(true)
    expect(wrapper.find('.meeting-form__title').text()).toBe('新建会议')
    expect(wrapper.find('img.meeting-form__mascot').exists()).toBe(true)
  })
})
