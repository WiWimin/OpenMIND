import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { askMeetingStream } from '@/api/chat'
import http from '@/api/client'
import { streamChat } from '@/api/chatStream'
import type { ChatResult } from '@/types/chat'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  apiBaseUrl: '/api/v1',
}))

const post = vi.mocked(http.post)
const fetchMock = vi.fn()

const META_FRAME =
  'event: meta\ndata: {"insufficient_evidence":false,' +
  '"sources":[{"meeting_id":"mtg_1","material_id":"mat_1","record_id":null,"excerpt":"原文片段"}],' +
  '"model":"gpt-x"}\n\n'
const DONE_FRAME =
  'event: done\ndata: {"answer":"你好","usage":{"input":3,"output":2},"latency_ms":42}\n\n'

function sseResponse(chunks: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

function jsonError(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function expectApiError(promise: Promise<unknown>, errorCode: string): Promise<void> {
  await expect(promise).rejects.toMatchObject({ status: 'error', error_code: errorCode })
}

describe('chatStream api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', fetchMock)
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses fragmented SSE frames, ignores ping comments, and accumulates the answer', async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        // 首帧在事件中途切块，验证跨 chunk 缓冲
        `${META_FRAME}event: del`,
        'ta\ndata: {"text":"你"}\n\n',
        ': ping\n\nevent: delta\ndata: {"text":"好"}\n\n',
        DONE_FRAME,
      ]),
    )
    const onMeta = vi.fn()
    const onDelta = vi.fn()
    const onDone = vi.fn()

    const result = await streamChat('mtg_1', { question: '结论？' }, { onMeta, onDelta, onDone })

    expect(onMeta).toHaveBeenCalledTimes(1)
    expect(onMeta.mock.calls[0][0]).toMatchObject({ model: 'gpt-x', insufficient_evidence: false })
    expect(onDelta.mock.calls.map(([text]) => text)).toEqual(['你', '好'])
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(result.answer).toBe('你好')
    expect(result.meta?.sources[0].excerpt).toBe('原文片段')
  })

  it('sends JSON body and the stored auth token', async () => {
    fetchMock.mockResolvedValue(sseResponse([DONE_FRAME]))
    window.localStorage.setItem('openmind.auth.token', 'tk-1')

    await streamChat('mtg_1', { question: '结论？' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/meetings/mtg_1/chat/stream')
    expect(init).toMatchObject({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer tk-1' }),
      body: JSON.stringify({ question: '结论？' }),
    })
  })

  it('maps HTTP 401 without body to AUTH_REQUIRED', async () => {
    fetchMock.mockResolvedValue(new Response('', { status: 401 }))

    await expectApiError(streamChat('mtg_1', { question: '?' }), 'AUTH_REQUIRED')
  })

  it('maps HTTP 404 error body to RESOURCE_NOT_FOUND', async () => {
    fetchMock.mockResolvedValue(
      jsonError(404, {
        status: 'error',
        error_code: 'RESOURCE_NOT_FOUND',
        message: '会议不存在',
        retryable: false,
      }),
    )

    await expectApiError(streamChat('mtg_1', { question: '?' }), 'RESOURCE_NOT_FOUND')
  })

  it('throws the error event payload after the stream has started', async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        META_FRAME,
        'event: delta\ndata: {"text":"第一段"}\n\n',
        'event: error\ndata: {"status":"error","error_code":"MODEL_TIMEOUT","message":"模型服务超时","retryable":true}\n\n',
      ]),
    )
    const onDelta = vi.fn()

    await expect(streamChat('mtg_1', { question: '?' }, { onDelta })).rejects.toMatchObject({
      error_code: 'MODEL_TIMEOUT',
      retryable: true,
    })
    expect(onDelta).toHaveBeenCalledTimes(1)
  })

  it('throws NETWORK_ERROR when the stream ends without a done frame', async () => {
    fetchMock.mockResolvedValue(sseResponse(['event: delta\ndata: {"text":"半途"}\n\n']))

    await expectApiError(streamChat('mtg_1', { question: '?' }), 'NETWORK_ERROR')
  })

  it('passes the abort signal through to fetch', async () => {
    fetchMock.mockResolvedValue(sseResponse([DONE_FRAME]))
    const controller = new AbortController()

    await streamChat('mtg_1', { question: '?' }, { signal: controller.signal })

    expect(fetchMock.mock.calls[0][1]).toMatchObject({ signal: controller.signal })
  })
})

describe('askMeetingStream', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', fetchMock)
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const syncResult: ChatResult = {
    answer: '同步回答',
    sources: [{ meeting_id: 'mtg_1', material_id: null, record_id: null, excerpt: '片段' }],
    insufficient_evidence: false,
  }

  it('returns the accumulated stream result as a ChatResult', async () => {
    fetchMock.mockResolvedValue(sseResponse([META_FRAME, 'event: delta\ndata: {"text":"你好"}\n\n', DONE_FRAME]))

    const result = await askMeetingStream('mtg_1', { question: '结论？' })

    expect(result).toEqual({
      answer: '你好',
      sources: [
        { meeting_id: 'mtg_1', material_id: 'mat_1', record_id: null, excerpt: '原文片段' },
      ],
      insufficient_evidence: false,
      file: null,
    })
    expect(post).not.toHaveBeenCalled()
  })

  it('falls back to the sync endpoint on 404 (SSE disabled or meeting missing)', async () => {
    fetchMock.mockResolvedValue(
      jsonError(404, {
        status: 'error',
        error_code: 'RESOURCE_NOT_FOUND',
        message: '流式问答未启用',
        retryable: false,
      }),
    )
    post.mockResolvedValue(response({ status: 'success', data: syncResult }))

    const result = await askMeetingStream('mtg_1', { question: '结论？' })

    expect(result).toEqual(syncResult)
    expect(post).toHaveBeenCalledWith(
      '/meetings/mtg_1/chat',
      { question: '结论？' },
      { timeout: expect.any(Number) },
    )
  })

  it('rethrows non-404 errors without falling back', async () => {
    fetchMock.mockResolvedValue(
      jsonError(500, { status: 'error', error_code: 'INTERNAL_ERROR', message: '出错', retryable: true }),
    )

    await expectApiError(askMeetingStream('mtg_1', { question: '?' }), 'INTERNAL_ERROR')
    expect(post).not.toHaveBeenCalled()
  })

  it('forwards meta and delta to the caller handlers', async () => {
    fetchMock.mockResolvedValue(sseResponse([META_FRAME, 'event: delta\ndata: {"text":"正文"}\n\n', DONE_FRAME]))
    const onMeta = vi.fn()
    const onDelta = vi.fn()

    await askMeetingStream('mtg_1', { question: '?' }, { onMeta, onDelta })

    expect(onMeta).toHaveBeenCalledTimes(1)
    expect(onDelta).toHaveBeenCalledWith('正文')
  })
})
