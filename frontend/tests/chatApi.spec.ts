import { beforeEach, describe, expect, it, vi } from 'vitest'

import { askMeeting, organizeRecords } from '@/api/chat'
import http from '@/api/client'
import type { ChatResult } from '@/types/chat'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const post = vi.mocked(http.post)

const chatResult: ChatResult = {
  answer: '上次会议决定了……',
  sources: [{ meeting_id: 'mtg_1', material_id: 'mat_1', record_id: null, excerpt: '片段' }],
  insufficient_evidence: false,
}

describe('chat api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('asks a meeting question and unwraps the result', async () => {
    post.mockResolvedValue(response({ status: 'success', data: chatResult }))

    await expect(askMeeting('mtg_1', { question: '决定了什么？' })).resolves.toEqual(chatResult)
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/chat', { question: '决定了什么？' })
  })

  it('organizes records', async () => {
    const organized = { organized_content: '整理后内容', source_record_ids: ['rec_1'] }
    post.mockResolvedValue(response({ status: 'success', data: organized }))

    await expect(organizeRecords('mtg_1', { record_ids: ['rec_1'] })).resolves.toEqual(organized)
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/organize', { record_ids: ['rec_1'] })
  })
})
