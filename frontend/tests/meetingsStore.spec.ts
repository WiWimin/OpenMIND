import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import { useMeetingsStore } from '@/stores/meetings'
import type { ListData } from '@/types/api'
import type { Meeting } from '@/types/meeting'

vi.mock('@/api/meetings', () => ({
  listMeetings: vi.fn(),
  createMeeting: vi.fn(),
  getMeeting: vi.fn(),
  updateMeeting: vi.fn(),
  deleteMeeting: vi.fn(),
  archiveMeeting: vi.fn(),
}))

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

function listOf(items: Meeting[]): ListData<Meeting> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

describe('meetings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('loads the meeting list', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    const store = useMeetingsStore()

    await store.fetchList()

    expect(store.items).toEqual([meeting])
    expect(store.pagination.total).toBe(1)
    expect(meetingsApi.listMeetings).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: undefined,
    })
  })

  it('applies the status filter and reloads from page 1', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([]))
    const store = useMeetingsStore()

    await store.setStatusFilter('archived')

    expect(store.filters.status).toBe('archived')
    expect(meetingsApi.listMeetings).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: 'archived',
    })
  })

  it('loads a meeting into current', async () => {
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    const store = useMeetingsStore()

    await store.fetchMeeting('mtg_1')

    expect(store.current).toEqual(meeting)
    expect(store.currentLoading).toBe(false)
  })

  it('captures detail errors', async () => {
    const failure = { error_code: 'RESOURCE_NOT_FOUND' }
    vi.mocked(meetingsApi.getMeeting).mockRejectedValue(failure)
    const store = useMeetingsStore()

    await store.fetchMeeting('missing')

    expect(store.currentError).toBe(failure)
  })

  it('creates a meeting then refreshes the list', async () => {
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(meeting)
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    const store = useMeetingsStore()

    const created = await store.createMeeting({ title: '项目周会' })

    expect(created).toEqual(meeting)
    expect(meetingsApi.listMeetings).toHaveBeenCalledTimes(1)
    expect(store.items).toEqual([meeting])
  })

  it('syncs an updated meeting into the list and current', async () => {
    const updated = { ...meeting, title: '新标题' }
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    vi.mocked(meetingsApi.updateMeeting).mockResolvedValue(updated)
    const store = useMeetingsStore()
    await store.fetchList()
    await store.fetchMeeting('mtg_1')

    await store.updateMeeting('mtg_1', { title: '新标题' })

    expect(store.items[0].title).toBe('新标题')
    expect(store.current?.title).toBe('新标题')
  })

  it('archives a meeting and updates its status', async () => {
    const archived = { ...meeting, status: 'archived' as const }
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    vi.mocked(meetingsApi.archiveMeeting).mockResolvedValue(archived)
    const store = useMeetingsStore()
    await store.fetchList()

    await store.archiveMeeting('mtg_1')

    expect(store.items[0].status).toBe('archived')
  })

  it('deletes a meeting and refreshes the list', async () => {
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([meeting]))
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meeting)
    vi.mocked(meetingsApi.deleteMeeting).mockResolvedValue({ deleted: true, meeting_id: 'mtg_1' })
    const store = useMeetingsStore()
    await store.fetchList()
    await store.fetchMeeting('mtg_1')
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf([]))

    await store.deleteMeeting('mtg_1')

    expect(store.current).toBeNull()
    expect(store.items).toEqual([])
  })
})
