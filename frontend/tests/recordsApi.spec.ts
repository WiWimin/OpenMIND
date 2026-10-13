import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { createRecord, deleteRecord, listRecords, updateRecord } from '@/api/records'
import type { ListData } from '@/types/api'
import type { MeetingRecord } from '@/types/record'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)
const del = vi.mocked(http.delete)

const record: MeetingRecord = {
  record_id: 'rec_1',
  meeting_id: 'mtg_1',
  content: '讨论记录正文',
  record_type: 'manual',
  source_material_id: null,
  created_at: '2026-10-01T09:15:00+08:00',
  updated_at: '2026-10-01T09:15:00+08:00',
}

describe('records api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists records with pagination params', async () => {
    const list: ListData<MeetingRecord> = {
      items: [record],
      pagination: { page: 2, page_size: 20, total: 21, total_pages: 2 },
    }
    get.mockResolvedValue(response(list))

    await expect(listRecords('mtg_1', { page: 2 })).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/records', { params: { page: 2 } })
  })

  it('creates a record', async () => {
    post.mockResolvedValue(response(record))

    await expect(createRecord('mtg_1', { content: '正文', record_type: 'manual' })).resolves.toEqual(
      record,
    )
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/records', {
      content: '正文',
      record_type: 'manual',
    })
  })

  it('updates a record', async () => {
    patch.mockResolvedValue(response({ status: 'success', data: record }))

    await expect(updateRecord('rec_1', { content: '新内容' })).resolves.toEqual(record)
    expect(patch).toHaveBeenCalledWith('/records/rec_1', { content: '新内容' })
  })

  it('deletes a record', async () => {
    const deleted = { deleted: true as const, record_id: 'rec_1' }
    del.mockResolvedValue(response({ status: 'success', data: deleted }))

    await expect(deleteRecord('rec_1')).resolves.toEqual(deleted)
    expect(del).toHaveBeenCalledWith('/records/rec_1')
  })
})
