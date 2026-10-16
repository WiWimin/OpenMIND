import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { extractIssues, listIssues, updateIssue } from '@/api/issues'
import type { ListData } from '@/types/api'
import type { OpenIssue } from '@/types/issue'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)

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

describe('issues api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('extracts issues from an items envelope', async () => {
    post.mockResolvedValue(response({ status: 'success', data: { items: [issue] } }))

    await expect(extractIssues('mtg_1', { record_ids: ['rec_1'] })).resolves.toEqual([issue])
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/issues/extract', {
      record_ids: ['rec_1'],
    }, { signal: undefined })
  })

  it('lists issues with pagination params', async () => {
    const list: ListData<OpenIssue> = {
      items: [issue],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listIssues('mtg_1')).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/issues', { params: {} })
  })

  it('updates an issue', async () => {
    patch.mockResolvedValue(response({ status: 'success', data: { ...issue, status: 'resolved' } }))

    await expect(updateIssue('iss_1', { status: 'resolved' })).resolves.toEqual({
      ...issue,
      status: 'resolved',
    })
    expect(patch).toHaveBeenCalledWith('/issues/iss_1', { status: 'resolved' })
  })
})
