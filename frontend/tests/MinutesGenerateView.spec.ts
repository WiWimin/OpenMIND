import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MinutesGenerateView from '@/views/newMeeting/MinutesGenerateView.vue'

const { routeState } = vi.hoisted(() => ({
  routeState: { query: { meetingId: 'mtg_1' } as Record<string, string>, hash: '' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/chat', () => ({
  askMeeting: vi.fn(),
  organizeRecords: vi.fn(),
}))

const meeting = {
  meeting_id: 'mtg_1',
  title: '项目周会',
  topic: null,
  meeting_time: null,
  status: 'scheduled' as const,
  created_at: '2026-11-05T09:00:00+08:00',
  updated_at: '2026-11-05T09:00:00+08:00',
  archived_at: null,
}

/** 只渲染 StageShell 的默认插槽（提供 meeting 上下文），其余子组件打桩 */
const StageShellStub = {
  name: 'StageShell',
  props: ['stage', 'title', 'description'],
  setup(_props: unknown, { slots }: { slots: Record<string, ((...args: unknown[]) => unknown) | undefined> }) {
    return () => slots.default?.({ meeting, meetingId: meeting.meeting_id })
  },
}

function mountView() {
  return mount(MinutesGenerateView, {
    global: {
      stubs: {
        StageShell: StageShellStub,
        AgentChat: true,
        ModePicker: true,
        ModelPickerPopover: true,
        TemplatePickerPopover: true,
        AgentDocDrawer: true,
      },
    },
  })
}

describe('MinutesGenerateView 页面结构', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    routeState.query = { meetingId: 'mtg_1' }
  })

  it('不再提供「查看全部产出」入口与产出区', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.minutes-page__produce-bar').exists()).toBe(false)
    expect(wrapper.find('.minutes-page__produce').exists()).toBe(false)
  })

  it('产出只通过聊天文件卡 → 文件打开页访问', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'AgentChat' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AgentDocDrawer' }).exists()).toBe(true)
  })
})
