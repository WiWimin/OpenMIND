import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as actionItemsApi from '@/api/actionItems'
import ActionItemSection from '@/components/ActionItemSection.vue'
import type { ActionItem, ActionItemStatus } from '@/types/actionItem'
import type { ListData } from '@/types/api'

vi.mock('@/api/actionItems', () => ({
  extractActionItems: vi.fn(),
  listActionItems: vi.fn(),
  getActionItem: vi.fn(),
  updateActionItem: vi.fn(),
  deleteActionItem: vi.fn(),
  confirmActionItem: vi.fn(),
  convertActionItemToTask: vi.fn(),
}))

function makeItem(status: ActionItemStatus, id = 'act_1'): ActionItem {
  return {
    action_id: id,
    meeting_id: 'mtg_1',
    content: '完成接口联调',
    assignee: '张三',
    due_date: '2026-10-05',
    status,
    source: { record_id: 'rec_1', excerpt: '张三负责完成联调' },
    created_at: '2026-10-01T10:05:00+08:00',
    updated_at: '2026-10-01T10:05:00+08:00',
  }
}

function listOf(items: ActionItem[]): ListData<ActionItem> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(): VueWrapper {
  return mount(ActionItemSection, { props: { meetingId: 'mtg_1' } })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('ActionItemSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows the empty state', async () => {
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有行动项')
  })

  it('lists items with their status and source', async () => {
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(listOf([makeItem('pending_confirmation')]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('完成接口联调')
    expect(wrapper.text()).toContain('待确认')
    expect(wrapper.text()).toContain('张三负责完成联调')
    expect(button(wrapper, '确认')).toBeTruthy()
  })

  it('extracts action items then refreshes', async () => {
    vi.mocked(actionItemsApi.listActionItems)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([makeItem('pending_confirmation')]))
    vi.mocked(actionItemsApi.extractActionItems).mockResolvedValue([])
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '提取行动项')?.trigger('click')
    await flushPromises()

    expect(actionItemsApi.extractActionItems).toHaveBeenCalledWith('mtg_1', { record_ids: [] })
    expect(wrapper.text()).toContain('完成接口联调')
  })

  it('confirms a pending action item', async () => {
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(listOf([makeItem('pending_confirmation')]))
    vi.mocked(actionItemsApi.confirmActionItem).mockResolvedValue(makeItem('confirmed'))
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '确认')?.trigger('click')
    await flushPromises()

    expect(actionItemsApi.confirmActionItem).toHaveBeenCalledWith('act_1')
  })

  it('converts a confirmed action item to a task', async () => {
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(listOf([makeItem('confirmed')]))
    vi.mocked(actionItemsApi.convertActionItemToTask).mockResolvedValue({
      task_id: 'tsk_1',
      user_id: 'usr_1',
      meeting_id: 'mtg_1',
      action_id: 'act_1',
      title: '完成接口联调',
      status: 'todo',
      due_date: '2026-10-05',
      created_at: '2026-10-01T10:10:00+08:00',
      updated_at: '2026-10-01T10:10:00+08:00',
    })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '转为我的个人任务')?.trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(actionItemsApi.convertActionItemToTask).toHaveBeenCalledWith('act_1', {
      title: '完成接口联调',
      due_date: '2026-10-05',
    })
  })
})
