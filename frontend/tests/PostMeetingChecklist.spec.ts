import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as actionItemsApi from '@/api/actionItems'
import * as issuesApi from '@/api/issues'
import * as minutesApi from '@/api/minutes'
import type { ActionItem } from '@/types/actionItem'
import type { OpenIssue } from '@/types/issue'
import type { Minutes } from '@/types/minutes'
import PostMeetingChecklist from '@/components/PostMeetingChecklist.vue'

vi.mock('@/api/minutes', () => ({
  listMinutes: vi.fn(),
  generateMinutes: vi.fn(),
  getMinutes: vi.fn(),
  updateMinutes: vi.fn(),
  confirmMinutes: vi.fn(),
}))

vi.mock('@/api/actionItems', () => ({
  extractActionItems: vi.fn(),
  listActionItems: vi.fn(),
  getActionItem: vi.fn(),
  updateActionItem: vi.fn(),
  deleteActionItem: vi.fn(),
  confirmActionItem: vi.fn(),
  convertActionItemToTask: vi.fn(),
}))

vi.mock('@/api/issues', () => ({
  extractIssues: vi.fn(),
  listIssues: vi.fn(),
  updateIssue: vi.fn(),
}))

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
    props: ['to'],
  },
}))

const minutes: Minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '纪要内容',
  status: 'draft',
  version: 1,
  source_record_ids: [],
  created_at: '2026-10-01T10:00:00+08:00',
  updated_at: '2026-10-01T10:00:00+08:00',
}

function actionItem(status: ActionItem['status']): ActionItem {
  return {
    action_id: `act_${status}`,
    meeting_id: 'mtg_1',
    content: '行动项',
    assignee: null,
    due_date: null,
    status,
    source: { record_id: null, excerpt: null },
    created_at: '2026-10-01T10:00:00+08:00',
    updated_at: '2026-10-01T10:00:00+08:00',
  }
}

function issue(status: OpenIssue['status']): OpenIssue {
  return {
    issue_id: `iss_${status}`,
    meeting_id: 'mtg_1',
    description: '问题',
    status,
    follow_up: null,
    source: { record_id: null },
    created_at: '2026-10-01T10:00:00+08:00',
    updated_at: '2026-10-01T10:00:00+08:00',
  }
}

function listOf<T>(items: T[]) {
  return { items, pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 } }
}

function mountChecklist() {
  return mount(PostMeetingChecklist, { props: { meetingId: 'mtg_1' } })
}

describe('PostMeetingChecklist', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([]))
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(listOf([]))
    vi.mocked(issuesApi.listIssues).mockResolvedValue(listOf([]))
  })

  it('shows pending counts and jumps to the related tab', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(
      listOf([actionItem('pending_confirmation'), actionItem('confirmed')]),
    )
    vi.mocked(issuesApi.listIssues).mockResolvedValue(listOf([issue('open')]))
    const wrapper = mountChecklist()
    await flushPromises()

    expect(wrapper.text()).toContain('草稿待确认')
    expect(wrapper.text()).toContain('1 项')

    const issueJump = wrapper.findAll('button').find((button) => button.text() === '去处理')
    await issueJump?.trigger('click')

    expect(wrapper.emitted('go-to-tab')?.[0]).toEqual(['issues'])
  })

  it('reports everything finished when confirmed with no pending items', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([{ ...minutes, status: 'confirmed' }]))
    vi.mocked(actionItemsApi.listActionItems).mockResolvedValue(
      listOf([actionItem('confirmed'), actionItem('converted')]),
    )
    vi.mocked(issuesApi.listIssues).mockResolvedValue(listOf([issue('resolved')]))
    const wrapper = mountChecklist()
    await flushPromises()

    expect(wrapper.text()).toContain('本次会议已收尾')
    expect(wrapper.text()).toContain('已确认')
    expect(wrapper.text()).toContain('已转个人任务')
  })

  it('shows the generate action when there is no minutes yet', async () => {
    const wrapper = mountChecklist()
    await flushPromises()

    expect(wrapper.text()).toContain('未生成')
    const generate = wrapper.findAll('button').find((button) => button.text() === '生成纪要')
    await generate?.trigger('click')

    expect(wrapper.emitted('go-to-tab')?.[0]).toEqual(['minutes'])
  })

  it('surfaces a load error and retries', async () => {
    vi.mocked(minutesApi.listMinutes).mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountChecklist()
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(true)

    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([]))
    const retry = wrapper.get('.error-message button')
    await retry.trigger('click')
    await flushPromises()

    expect(wrapper.find('.error-message').exists()).toBe(false)
  })
})
