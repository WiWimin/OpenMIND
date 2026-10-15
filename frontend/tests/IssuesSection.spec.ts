import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as issuesApi from '@/api/issues'
import IssuesSection from '@/components/IssuesSection.vue'
import type { ListData } from '@/types/api'
import type { OpenIssue } from '@/types/issue'

vi.mock('@/api/issues', () => ({
  extractIssues: vi.fn(),
  listIssues: vi.fn(),
  updateIssue: vi.fn(),
}))

const issue: OpenIssue = {
  issue_id: 'iss_1',
  meeting_id: 'mtg_1',
  description: '接口联调时间可能延期',
  status: 'open',
  follow_up: '确认依赖接口完成时间',
  source: { record_id: 'rec_1' },
  created_at: '2026-10-01T10:20:00+08:00',
  updated_at: '2026-10-01T10:20:00+08:00',
}

function listOf(items: OpenIssue[]): ListData<OpenIssue> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(): VueWrapper {
  return mount(IssuesSection, { props: { meetingId: 'mtg_1' } })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('IssuesSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows the empty state', async () => {
    vi.mocked(issuesApi.listIssues).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有未解决问题')
  })

  it('lists issues with status, follow-up and source', async () => {
    vi.mocked(issuesApi.listIssues).mockResolvedValue(listOf([issue]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('接口联调时间可能延期')
    expect(wrapper.text()).toContain('待处理')
    expect(wrapper.text()).toContain('确认依赖接口完成时间')
    expect(wrapper.text()).toContain('来源 rec_1')
  })

  it('extracts issues then refreshes', async () => {
    vi.mocked(issuesApi.listIssues)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([issue]))
    vi.mocked(issuesApi.extractIssues).mockResolvedValue([])
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '提取未解决问题')?.trigger('click')
    await flushPromises()

    expect(issuesApi.extractIssues).toHaveBeenCalledWith('mtg_1', { record_ids: [] }, expect.anything())
    expect(wrapper.text()).toContain('接口联调时间可能延期')
  })

  it('edits status and follow-up', async () => {
    vi.mocked(issuesApi.listIssues).mockResolvedValue(listOf([issue]))
    vi.mocked(issuesApi.updateIssue).mockResolvedValue({ ...issue, status: 'resolved' })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '编辑')?.trigger('click')
    await wrapper.get('#issue-status').setValue('resolved')
    await wrapper.get('#issue-follow-up').setValue('已确认时间')
    await button(wrapper, '保存')?.trigger('click')
    await flushPromises()

    expect(issuesApi.updateIssue).toHaveBeenCalledWith('iss_1', {
      status: 'resolved',
      follow_up: '已确认时间',
    })
  })
})
