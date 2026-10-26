import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import {
  confirmMinutes,
  generateMinutes,
  getMinutes,
  listMinutes,
  updateMinutes,
} from '@/api/minutes'
import type { ListData } from '@/types/api'
import type { Minutes } from '@/types/minutes'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)

const minutes: Minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '会议纪要草稿',
  status: 'draft',
  version: 1,
  template: 'standard',
  source_record_ids: ['rec_1'],
  source_material_ids: [],
  created_at: '2026-10-01T10:00:00+08:00',
  updated_at: '2026-10-01T10:00:00+08:00',
}

describe('minutes api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('generates minutes', async () => {
    post.mockResolvedValue(response(minutes))

    await expect(generateMinutes('mtg_1', { record_ids: ['rec_1'] })).resolves.toEqual(minutes)
    expect(post).toHaveBeenCalledWith(
      '/meetings/mtg_1/minutes/generate',
      { record_ids: ['rec_1'] },
      { signal: undefined, timeout: LONG_REQUEST_TIMEOUT_MS },
    )
  })

  it('lists minutes with pagination params', async () => {
    const list: ListData<Minutes> = {
      items: [minutes],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listMinutes('mtg_1')).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/minutes', { params: {} })
  })

  it('gets a minutes record', async () => {
    get.mockResolvedValue(response({ status: 'success', data: minutes }))

    await expect(getMinutes('min_1')).resolves.toEqual(minutes)
    expect(get).toHaveBeenCalledWith('/minutes/min_1')
  })

  it('updates minutes content', async () => {
    patch.mockResolvedValue(response(minutes))

    await expect(updateMinutes('min_1', { content: '新纪要' })).resolves.toEqual(minutes)
    expect(patch).toHaveBeenCalledWith('/minutes/min_1', { content: '新纪要' })
  })

  it('confirms minutes', async () => {
    post.mockResolvedValue(response({ status: 'success', data: { ...minutes, status: 'confirmed' } }))

    await expect(confirmMinutes('min_1')).resolves.toEqual({ ...minutes, status: 'confirmed' })
    expect(post).toHaveBeenCalledWith('/minutes/min_1/confirm')
  })
})
