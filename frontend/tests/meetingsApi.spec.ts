import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import {
  archiveMeeting,
  createMeeting,
  deleteMeeting,
  getMeeting,
  listMeetings,
  updateMeeting,
} from '@/api/meetings'
import type { ListData } from '@/types/api'
import type { Meeting } from '@/types/meeting'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)
const del = vi.mocked(http.delete)

const meeting: Meeting = {
  meeting_id: 'mtg_1',
  title: '项目周会',
  topic: '进度与风险',
  meeting_time: '2026-10-02T14:00:00+08:00',
  status: 'scheduled',
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
  archived_at: null,
}

describe('meetings api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists meetings with pagination and status filters', async () => {
    const list: ListData<Meeting> = {
      items: [meeting],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listMeetings({ page: 1, status: 'scheduled' })).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings', { params: { page: 1, status: 'scheduled' } })
  })

  it('creates a meeting', async () => {
    post.mockResolvedValue(response(meeting))

    await expect(createMeeting({ title: '项目周会', topic: '进度与风险' })).resolves.toEqual(meeting)
    expect(post).toHaveBeenCalledWith('/meetings', { title: '项目周会', topic: '进度与风险' })
  })

  it('gets a meeting', async () => {
    get.mockResolvedValue(response({ status: 'success', data: meeting }))

    await expect(getMeeting('mtg_1')).resolves.toEqual(meeting)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1')
  })

  it('updates a meeting', async () => {
    patch.mockResolvedValue(response(meeting))

    await expect(updateMeeting('mtg_1', { title: '新标题' })).resolves.toEqual(meeting)
    expect(patch).toHaveBeenCalledWith('/meetings/mtg_1', { title: '新标题' })
  })

  it('deletes a meeting', async () => {
    const deleted = { deleted: true as const, meeting_id: 'mtg_1' }
    del.mockResolvedValue(response({ status: 'success', data: deleted }))

    await expect(deleteMeeting('mtg_1')).resolves.toEqual(deleted)
    expect(del).toHaveBeenCalledWith('/meetings/mtg_1')
  })

  it('archives a meeting', async () => {
    post.mockResolvedValue(response({ status: 'success', data: { ...meeting, status: 'archived' } }))

    await expect(archiveMeeting('mtg_1')).resolves.toEqual({ ...meeting, status: 'archived' })
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/archive')
  })
})
