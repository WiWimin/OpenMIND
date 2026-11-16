import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { createActionItem } from '@/api/actionItems'
import { downloadAudio, uploadAudio } from '@/api/audio'
import { createIssue } from '@/api/issues'
import { downloadMaterial, uploadMaterial } from '@/api/materials'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ActionItem } from '@/types/actionItem'
import type { MeetingAudio } from '@/types/audio'
import type { Issue } from '@/types/issue'
import type { Material } from '@/types/material'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)

const material: Material = {
  material_id: 'mat_1',
  meeting_id: 'mtg_1',
  file_name: '方案.pdf',
  type: 'pdf',
  source: null,
  processing_status: 'uploaded',
  parse_error: null,
  file_size: 12,
  created_at: '2026-10-01T09:00:00+08:00',
}

const audio: MeetingAudio = {
  audio_id: 'aud_1',
  meeting_id: 'mtg_1',
  file_name: '录音.m4a',
  type: 'm4a',
  file_size: 34,
  status: 'transcribed',
  transcript: '大家好',
  segments: null,
  error: null,
  record_id: null,
  created_at: '2026-10-01T09:30:00+08:00',
  updated_at: '2026-10-01T09:35:00+08:00',
}

const issue: Issue = {
  issue_id: 'iss_1',
  meeting_id: 'mtg_1',
  description: '预算未确认',
  status: 'open',
  follow_up: null,
  source: { record_id: null },
  created_at: '2026-10-01T10:00:00+08:00',
  updated_at: '2026-10-01T10:00:00+08:00',
}

const actionItem: ActionItem = {
  action_id: 'act_1',
  meeting_id: 'mtg_1',
  content: '完成接口联调',
  assignee: null,
  due_date: null,
  status: 'pending_confirmation',
  source: { record_id: null, excerpt: null },
  created_at: '2026-10-01T10:05:00+08:00',
  updated_at: '2026-10-01T10:05:00+08:00',
}

describe('api 本地工作区双向同步封装', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('downloadMaterial 以 blob 响应请求下载地址并返回 Blob', async () => {
    const blob = new Blob(['pdf-bytes'], { type: 'application/pdf' })
    get.mockResolvedValue(response(blob))

    await expect(downloadMaterial('mat_1')).resolves.toBe(blob)
    expect(get).toHaveBeenCalledWith('/materials/mat_1/download', {
      responseType: 'blob',
      timeout: LONG_REQUEST_TIMEOUT_MS,
    })
  })

  it('downloadAudio 以 blob 响应请求下载地址并返回 Blob', async () => {
    const blob = new Blob(['audio-bytes'], { type: 'audio/mp4' })
    get.mockResolvedValue(response(blob))

    await expect(downloadAudio('aud_1')).resolves.toBe(blob)
    expect(get).toHaveBeenCalledWith('/audio/aud_1/download', {
      responseType: 'blob',
      timeout: LONG_REQUEST_TIMEOUT_MS,
    })
  })

  it('createIssue 把 client_op_id 放进 JSON body', async () => {
    post.mockResolvedValue(response(issue))

    await expect(
      createIssue('mtg_1', {
        description: '预算未确认',
        follow_up: '下周复核',
        client_op_id: 'op_issue_1',
      }),
    ).resolves.toEqual(issue)
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/issues', {
      description: '预算未确认',
      follow_up: '下周复核',
      client_op_id: 'op_issue_1',
    })
  })

  it('createActionItem 把 client_op_id 放进 JSON body', async () => {
    post.mockResolvedValue(response(actionItem))

    await expect(
      createActionItem('mtg_1', {
        content: '完成接口联调',
        assignee: '张三',
        due_date: '2026-10-05',
        client_op_id: 'op_act_1',
      }),
    ).resolves.toEqual(actionItem)
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/action-items', {
      content: '完成接口联调',
      assignee: '张三',
      due_date: '2026-10-05',
      client_op_id: 'op_act_1',
    })
  })

  it('uploadMaterial 把 client_op_id 放进 FormData', async () => {
    post.mockResolvedValue(response(material))
    const file = new File(['x'], 'a.pdf', { type: 'application/pdf' })

    await uploadMaterial('mtg_1', { file, client_op_id: 'op_mat_1' })

    const [url, form] = post.mock.calls[0]
    expect(url).toBe('/meetings/mtg_1/materials')
    expect((form as FormData).get('file')).toBe(file)
    expect((form as FormData).get('client_op_id')).toBe('op_mat_1')
  })

  it('uploadAudio 把 client_op_id 放进 FormData', async () => {
    post.mockResolvedValue(response(audio))
    const file = new File(['x'], 'a.m4a', { type: 'audio/mp4' })

    await uploadAudio('mtg_1', file, 'op_aud_1')

    const [url, form] = post.mock.calls[0]
    expect(url).toBe('/meetings/mtg_1/audio')
    expect((form as FormData).get('file')).toBe(file)
    expect((form as FormData).get('client_op_id')).toBe('op_aud_1')
  })
})
