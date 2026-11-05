import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as minutesApi from '@/api/minutes'
import MinutesGenerateView from '@/views/newMeeting/MinutesGenerateView.vue'

const { routeState } = vi.hoisted(() => ({
  routeState: { query: { meetingId: 'mtg_1' } as Record<string, string>, hash: '' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/minutes', () => ({
  listMinutes: vi.fn(),
  generateMinutes: vi.fn(),
}))

vi.mock('@/api/actionItems', () => ({
  extractActionItems: vi.fn(),
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

const minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '## 本周结论\n\n- 完成灰度检查',
  template: 'standard' as const,
  version: 1,
  status: 'draft' as const,
  source_record_ids: [],
  source_material_ids: [],
  created_at: '2026-11-05T09:10:00+08:00',
  updated_at: '2026-11-05T09:10:00+08:00',
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
        MinutesSection: true,
        ActionItemSection: true,
      },
    },
  })
}

describe('MinutesGenerateView 产出区', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    routeState.query = { meetingId: 'mtg_1' }
    vi.mocked(minutesApi.listMinutes).mockResolvedValue({
      items: [minutes],
      pagination: { page: 1, page_size: 1, total: 1, total_pages: 1 },
    })
  })

  it('已有纪要时进入页面即展示产出区，并默认停在纪要标签', async () => {
    const wrapper = mountView()
    await flushPromises()

    const produce = wrapper.find('.minutes-page__produce')
    expect(produce.exists()).toBe(true)

    const tabs = wrapper.findAll('.minutes-page__produce-tab').map((node) => node.text())
    expect(tabs).toEqual(['纪要', '行动项'])
    expect(wrapper.findAll('.minutes-page__produce-tab')[0].classes()).toContain(
      'minutes-page__produce-tab--active',
    )
    // 打桩的纪要区块已挂载
    expect(wrapper.findComponent({ name: 'MinutesSection' }).exists()).toBe(true)
  })

  it('可切换到行动项标签并收起产出区', async () => {
    const wrapper = mountView()
    await flushPromises()

    const actionsTab = wrapper
      .findAll('.minutes-page__produce-tab')
      .find((node) => node.text() === '行动项')
    await actionsTab?.trigger('click')

    expect(wrapper.findComponent({ name: 'ActionItemSection' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'MinutesSection' }).exists()).toBe(false)

    const toggle = wrapper.get('.minutes-page__produce-toggle')
    expect(toggle.text()).toBe('收起')
    await toggle.trigger('click')
    expect(toggle.text()).toBe('展开')
    expect(wrapper.find('.minutes-page__produce').classes()).toContain(
      'minutes-page__produce--collapsed',
    )
  })

  it('没有纪要时不展示产出区', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue({
      items: [],
      pagination: { page: 1, page_size: 1, total: 0, total_pages: 0 },
    })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.minutes-page__produce').exists()).toBe(false)
  })
})
