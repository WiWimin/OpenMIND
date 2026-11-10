import { beforeEach, describe, expect, it, vi } from 'vitest'

import { retryAudio } from '@/api/audio'
import http from '@/api/client'
import { extractJob, requireResourceId, waitForJob, type AsyncJob } from '@/api/jobs'
import { uploadDocument } from '@/api/knowledge'
import { uploadMaterial } from '@/api/materials'
import { generateMinutes } from '@/api/minutes'
import { generatePreparation } from '@/api/preparations'
import type { MeetingAudio } from '@/types/audio'
import type { KnowledgeDocument } from '@/types/knowledge'
import type { Material } from '@/types/material'
import type { Minutes } from '@/types/minutes'
import type { Preparation } from '@/types/preparation'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)

function job(overrides: Partial<AsyncJob> = {}): AsyncJob {
  return {
    job_id: 'job_1',
    job_type: 'material_parse',
    status: 'succeeded',
    resource_type: 'material',
    resource_id: 'mat_1',
    progress: 100,
    error_code: null,
    error_message: null,
    created_at: '2026-11-10T09:00:00+08:00',
    started_at: '2026-11-10T09:00:01+08:00',
    finished_at: '2026-11-10T09:00:02+08:00',
    ...overrides,
  }
}

function accepted(j: AsyncJob) {
  return response({ status: 'success', data: { job: j } })
}

const material: Material = {
  material_id: 'mat_1',
  meeting_id: 'mtg_1',
  file_name: '方案.pdf',
  type: 'pdf',
  source: null,
  processing_status: 'processed',
  parse_error: null,
  created_at: '2026-10-01T09:00:00+08:00',
}

const audio: MeetingAudio = {
  audio_id: 'aud_1',
  meeting_id: 'mtg_1',
  file_name: 'meeting.mp3',
  type: 'mp3',
  status: 'transcribed',
  transcript: '转写文本',
  segments: null,
  error: null,
  record_id: null,
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
}

const document: KnowledgeDocument = {
  document_id: 'kdoc_1',
  file_name: 'notes.txt',
  type: 'txt',
  processing_status: 'processed',
  parse_error: null,
  created_at: '2026-10-01T09:00:00+08:00',
}

const minutes: Minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '会议纪要正文',
  status: 'draft',
  version: 1,
  template: 'standard',
  source_record_ids: ['rec_1'],
  source_material_ids: [],
  created_at: '2026-10-01T10:00:00+08:00',
  updated_at: '2026-10-01T10:00:00+08:00',
}

const preparation: Preparation = {
  preparation_id: 'prep_1',
  meeting_id: 'mtg_1',
  summary: '会前准备摘要',
  checklist: ['确认议程'],
  status: 'draft',
  version: 1,
  created_at: '2026-10-01T09:20:00+08:00',
  updated_at: '2026-10-01T09:20:00+08:00',
}

describe('extractJob', () => {
  it('extracts the job from a 202 accepted payload', () => {
    expect(extractJob({ job: job() })).toMatchObject({ job_id: 'job_1' })
  })

  it('returns null for sync business objects and invalid payloads', () => {
    expect(extractJob(material)).toBeNull()
    expect(extractJob({ job: { status: 'succeeded' } })).toBeNull()
    expect(extractJob(null)).toBeNull()
    expect(extractJob('job')).toBeNull()
  })
})

describe('waitForJob', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('returns immediately when the job already succeeded', async () => {
    get.mockResolvedValue(response({ status: 'success', data: job() }))

    await expect(waitForJob('job_1', { intervalMs: 0 })).resolves.toMatchObject({
      job_id: 'job_1',
      status: 'succeeded',
    })
    expect(get).toHaveBeenCalledWith('/jobs/job_1', {})
  })

  it('polls pending → running → succeeded', async () => {
    get
      .mockResolvedValueOnce(response({ status: 'success', data: job({ status: 'pending', progress: 0 }) }))
      .mockResolvedValueOnce(response({ status: 'success', data: job({ status: 'running', progress: 60 }) }))
      .mockResolvedValueOnce(response({ status: 'success', data: job() }))

    await expect(waitForJob('job_1', { intervalMs: 0 })).resolves.toMatchObject({
      status: 'succeeded',
    })
    expect(get).toHaveBeenCalledTimes(3)
  })

  it('throws the job error code and message when the job failed', async () => {
    get.mockResolvedValue(
      response({
        status: 'success',
        data: job({
          status: 'failed',
          error_code: 'FILE_PARSE_FAILED',
          error_message: '文件解析失败，请检查文件是否损坏后重试',
        }),
      }),
    )

    await expect(waitForJob('job_1', { intervalMs: 0 })).rejects.toMatchObject({
      status: 'error',
      error_code: 'FILE_PARSE_FAILED',
      message: '文件解析失败，请检查文件是否损坏后重试',
    })
  })

  it('throws JOB_TIMEOUT when the job stays pending past the deadline', async () => {
    get.mockResolvedValue(response({ status: 'success', data: job({ status: 'pending' }) }))

    await expect(waitForJob('job_1', { intervalMs: 0, timeoutMs: 0 })).rejects.toMatchObject({
      error_code: 'JOB_TIMEOUT',
      retryable: true,
    })
  })

  it('throws an abort error when the signal is already aborted', async () => {
    const controller = new AbortController()
    controller.abort()

    await expect(waitForJob('job_1', { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(get).not.toHaveBeenCalled()
  })
})

describe('requireResourceId', () => {
  it('returns the linked resource id', () => {
    expect(requireResourceId(job())).toBe('mat_1')
  })

  it('throws INTERNAL_ERROR when a non-minutes job has no resource', () => {
    let caught: unknown = null
    try {
      requireResourceId(job({ resource_id: null }))
    } catch (error) {
      caught = error
    }
    expect(caught).toMatchObject({ error_code: 'INTERNAL_ERROR', retryable: true })
  })
})

describe('202 accepted uploads wait for the job then refetch the resource', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('uploadMaterial waits and refetches the material detail', async () => {
    post.mockResolvedValue(
      accepted(job({ job_type: 'material_parse', resource_type: 'material', resource_id: 'mat_1' })),
    )
    get.mockImplementation((url: string) => {
      if (url === '/jobs/job_1') {
        return Promise.resolve(response({ status: 'success', data: job() }))
      }
      if (url === '/materials/mat_1') {
        return Promise.resolve(response({ status: 'success', data: material }))
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })

    const file = new File(['x'], '方案.pdf', { type: 'application/pdf' })
    await expect(uploadMaterial('mtg_1', { file })).resolves.toEqual(material)
    expect(get.mock.calls.map(([url]) => url)).toEqual(['/jobs/job_1', '/materials/mat_1'])
  })

  it('uploadMaterial keeps the sync contract when no job is returned', async () => {
    post.mockResolvedValue(response({ status: 'success', data: material }))

    await expect(
      uploadMaterial('mtg_1', { file: new File(['x'], 'a.pdf') }),
    ).resolves.toEqual(material)
    expect(get).not.toHaveBeenCalled()
  })

  it('retryAudio waits and refetches the audio detail', async () => {
    post.mockResolvedValue(
      accepted(job({ job_type: 'audio_transcribe', resource_type: 'audio', resource_id: 'aud_1' })),
    )
    get.mockImplementation((url: string) => {
      if (url === '/jobs/job_1') {
        return Promise.resolve(
          response({ status: 'success', data: job({ resource_type: 'audio', resource_id: 'aud_1' }) }),
        )
      }
      if (url === '/audio/aud_1') {
        return Promise.resolve(response({ status: 'success', data: audio }))
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })

    await expect(retryAudio('aud_1')).resolves.toEqual(audio)
    expect(get.mock.calls.map(([url]) => url)).toEqual(['/jobs/job_1', '/audio/aud_1'])
  })

  it('uploadDocument waits and refetches the document detail', async () => {
    post.mockResolvedValue(
      accepted(
        job({
          job_type: 'knowledge_parse',
          resource_type: 'knowledge_document',
          resource_id: 'kdoc_1',
        }),
      ),
    )
    get.mockImplementation((url: string) => {
      if (url === '/jobs/job_1') {
        return Promise.resolve(
          response({
            status: 'success',
            data: job({ resource_type: 'knowledge_document', resource_id: 'kdoc_1' }),
          }),
        )
      }
      if (url === '/knowledge/documents/kdoc_1') {
        return Promise.resolve(response({ status: 'success', data: document }))
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })

    const file = new File(['x'], 'notes.txt', { type: 'text/plain' })
    await expect(uploadDocument(file)).resolves.toEqual(document)
    expect(get.mock.calls.map(([url]) => url)).toEqual([
      '/jobs/job_1',
      '/knowledge/documents/kdoc_1',
    ])
  })

  it('generatePreparation waits then refetches the placeholder preparation', async () => {
    post.mockResolvedValue(
      accepted(
        job({
          job_type: 'preparation_generate',
          resource_type: 'preparation',
          resource_id: 'prep_1',
        }),
      ),
    )
    get.mockImplementation((url: string) => {
      if (url === '/jobs/job_1') {
        return Promise.resolve(
          response({
            status: 'success',
            data: job({ resource_type: 'preparation', resource_id: 'prep_1' }),
          }),
        )
      }
      if (url === '/preparations/prep_1') {
        return Promise.resolve(response({ status: 'success', data: preparation }))
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })

    await expect(
      generatePreparation('mtg_1', { user_goal: '确认风险' }),
    ).resolves.toEqual(preparation)
    expect(get.mock.calls.map(([url]) => url)).toEqual([
      '/jobs/job_1',
      '/preparations/prep_1',
    ])
  })

  it('generateMinutes waits then takes the latest minutes from the list', async () => {
    // 纪要生成受理时 resource_id 为 null（api.md 1.9），成功后按列表首条取结果
    post.mockResolvedValue(
      accepted(
        job({
          job_type: 'minutes_generate',
          resource_type: 'minutes',
          resource_id: null,
        }),
      ),
    )
    get.mockImplementation((url: string) => {
      if (url === '/jobs/job_1') {
        return Promise.resolve(response({ status: 'success', data: job({ resource_id: null }) }))
      }
      if (url === '/meetings/mtg_1/minutes') {
        return Promise.resolve(
          response({
            status: 'success',
            data: {
              items: [minutes],
              pagination: { page: 1, page_size: 1, total: 1, total_pages: 1 },
            },
          }),
        )
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })

    await expect(generateMinutes('mtg_1', { record_ids: ['rec_1'] })).resolves.toEqual(minutes)
    expect(get.mock.calls.map(([url]) => url)).toEqual([
      '/jobs/job_1',
      '/meetings/mtg_1/minutes',
    ])
  })

  it('propagates a failed job from an upload without refetching', async () => {
    post.mockResolvedValue(
      accepted(
        job({
          status: 'failed',
          error_code: 'MODEL_TIMEOUT',
          error_message: '模型响应超时',
        }),
      ),
    )
    get.mockResolvedValue(
      response({
        status: 'success',
        data: job({ status: 'failed', error_code: 'MODEL_TIMEOUT', error_message: '模型响应超时' }),
      }),
    )

    const file = new File(['x'], 'a.pdf')
    await expect(uploadMaterial('mtg_1', { file })).rejects.toMatchObject({
      error_code: 'MODEL_TIMEOUT',
      message: '模型响应超时',
    })
    expect(get.mock.calls.map(([url]) => url)).toEqual(['/jobs/job_1'])
  })
})
