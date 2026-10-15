import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import {
  generatePreparation,
  getPreparation,
  listPreparations,
  updatePreparation,
} from '@/api/preparations'
import type { ListData } from '@/types/api'
import type { Preparation } from '@/types/preparation'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)

const preparation: Preparation = {
  preparation_id: 'prep_1',
  meeting_id: 'mtg_1',
  summary: '会议背景摘要',
  checklist: ['确认里程碑'],
  status: 'draft',
  version: 1,
  created_at: '2026-10-01T09:20:00+08:00',
  updated_at: '2026-10-01T09:20:00+08:00',
}

describe('preparations api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('generates a preparation', async () => {
    post.mockResolvedValue(response(preparation))

    await expect(generatePreparation('mtg_1', { user_goal: '确认风险' })).resolves.toEqual(
      preparation,
    )
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/prepare', { user_goal: '确认风险' }, {
      signal: undefined,
    })
  })

  it('lists preparations with pagination params', async () => {
    const list: ListData<Preparation> = {
      items: [preparation],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listPreparations('mtg_1')).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/preparations', { params: {} })
  })

  it('gets a preparation', async () => {
    get.mockResolvedValue(response({ status: 'success', data: preparation }))

    await expect(getPreparation('prep_1')).resolves.toEqual(preparation)
    expect(get).toHaveBeenCalledWith('/preparations/prep_1')
  })

  it('updates a preparation', async () => {
    patch.mockResolvedValue(response(preparation))

    await expect(updatePreparation('prep_1', { checklist: ['a'] })).resolves.toEqual(preparation)
    expect(patch).toHaveBeenCalledWith('/preparations/prep_1', { checklist: ['a'] })
  })
})
