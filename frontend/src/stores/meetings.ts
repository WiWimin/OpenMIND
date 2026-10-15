import { ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

import * as meetingsApi from '@/api/meetings'
import { useAsyncList } from '@/composables/useAsyncList'
import type {
  CreateMeetingPayload,
  Meeting,
  MeetingStatus,
  UpdateMeetingPayload,
} from '@/types/meeting'

export type MeetingStatusFilter = MeetingStatus | ''

export const useMeetingsStore = defineStore('meetings', () => {
  const filters = ref<{ status: MeetingStatusFilter }>({ status: '' })

  const list = useAsyncList<Meeting>({
    fetcher: ({ page, page_size }) =>
      meetingsApi.listMeetings({
        page,
        page_size,
        status: filters.value.status || undefined,
      }),
  })

  const current = ref<Meeting | null>(null)
  const currentLoading = ref(false)
  const currentError = shallowRef<unknown>(null)

  function fetchList(page?: number): Promise<void> {
    return list.load(page)
  }

  function setPage(page: number): Promise<void> {
    return list.setPage(page)
  }

  function setStatusFilter(status: MeetingStatusFilter): Promise<void> {
    filters.value.status = status
    return list.load(1)
  }

  function loadMore(): Promise<void> {
    return list.loadMore()
  }

  function syncInList(meeting: Meeting): void {
    const index = list.items.value.findIndex((item) => item.meeting_id === meeting.meeting_id)
    if (index !== -1) {
      list.items.value[index] = meeting
    }
  }

  async function fetchMeeting(meetingId: string): Promise<void> {
    currentLoading.value = true
    currentError.value = null
    try {
      current.value = await meetingsApi.getMeeting(meetingId)
    } catch (caught) {
      currentError.value = caught
    } finally {
      currentLoading.value = false
    }
  }

  async function createMeeting(payload: CreateMeetingPayload): Promise<Meeting> {
    const meeting = await meetingsApi.createMeeting(payload)
    await list.load(1)
    return meeting
  }

  async function updateMeeting(meetingId: string, payload: UpdateMeetingPayload): Promise<Meeting> {
    const meeting = await meetingsApi.updateMeeting(meetingId, payload)
    syncInList(meeting)
    if (current.value?.meeting_id === meetingId) {
      current.value = meeting
    }
    return meeting
  }

  async function deleteMeeting(meetingId: string): Promise<void> {
    await meetingsApi.deleteMeeting(meetingId)
    if (current.value?.meeting_id === meetingId) {
      current.value = null
    }
    await list.load()
  }

  async function archiveMeeting(meetingId: string): Promise<Meeting> {
    const meeting = await meetingsApi.archiveMeeting(meetingId)
    syncInList(meeting)
    if (current.value?.meeting_id === meetingId) {
      current.value = meeting
    }
    return meeting
  }

  return {
    items: list.items,
    pagination: list.pagination,
    loading: list.loading,
    error: list.error,
    filters,
    current,
    currentLoading,
    currentError,
    fetchList,
    setPage,
    setStatusFilter,
    loadMore,
    fetchMeeting,
    createMeeting,
    updateMeeting,
    deleteMeeting,
    archiveMeeting,
  }
})
