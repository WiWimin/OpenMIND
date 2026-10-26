import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import {
  confirmAudio,
  deleteAudio,
  listAudio,
  retryAudio,
  updateTranscript,
  uploadAudio,
} from '@/api/audio'
import type { ListData } from '@/types/api'
import type { MeetingAudio } from '@/types/audio'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)
const del = vi.mocked(http.delete)

const audio: MeetingAudio = {
  audio_id: 'aud_1',
  meeting_id: 'mtg_1',
  file_name: 'meeting.mp3',
  type: 'mp3',
  status: 'transcribed',
  transcript: '转写文本',
  error: null,
  record_id: null,
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
}

describe('audio api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists audio with pagination', async () => {
    const list: ListData<MeetingAudio> = {
      items: [audio],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listAudio('mtg_1', { page: 1 })).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/audio', { params: { page: 1 } })
  })

  it('uploads audio as multipart', async () => {
    post.mockResolvedValue(response(audio))
    const file = new File(['audio'], 'meeting.mp3', { type: 'audio/mpeg' })

    await expect(uploadAudio('mtg_1', file)).resolves.toEqual(audio)

    const [path, body, options] = post.mock.calls[0]
    expect(path).toBe('/meetings/mtg_1/audio')
    expect((body as FormData).get('file')).toBe(file)
    expect(options).toEqual({
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: LONG_REQUEST_TIMEOUT_MS,
    })
  })

  it('updates transcript', async () => {
    patch.mockResolvedValue(response({ ...audio, transcript: '修订' }))

    await expect(updateTranscript('aud_1', '修订')).resolves.toEqual({
      ...audio,
      transcript: '修订',
    })
    expect(patch).toHaveBeenCalledWith('/audio/aud_1', { transcript: '修订' })
  })

  it('retries and confirms audio', async () => {
    post.mockResolvedValue(response(audio))

    await expect(retryAudio('aud_1')).resolves.toEqual(audio)
    await expect(confirmAudio('aud_1')).resolves.toEqual(audio)
    expect(post).toHaveBeenCalledWith('/audio/aud_1/retry', undefined, {
      timeout: LONG_REQUEST_TIMEOUT_MS,
    })
    expect(post).toHaveBeenCalledWith('/audio/aud_1/confirm')
  })

  it('deletes audio', async () => {
    del.mockResolvedValue(response({ deleted: true, audio_id: 'aud_1' }))

    await expect(deleteAudio('aud_1')).resolves.toEqual({
      deleted: true,
      audio_id: 'aud_1',
    })
    expect(del).toHaveBeenCalledWith('/audio/aud_1')
  })
})
