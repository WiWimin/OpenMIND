import { beforeEach, describe, expect, it, vi } from 'vitest'

import { streamAgentTurn } from '@/api/agent'
import { streamChat } from '@/api/chatStream'
import type { ChatTrace } from '@/types/chat'

/** 构造 SSE 响应体：帧之间以空行分隔 */
function sseResponse(frames: string[]): Response {
  const body = frames.join('\n\n') + '\n\n'
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body))
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

const trace: ChatTrace = {
  stages: [
    { id: 'retrieve', label: '检索会议资料', status: 'done', detail: '命中 1 条' },
    { id: 'generate', label: '生成回答', status: 'running' },
  ],
  native_reasoning: false,
}

const fetchMock = vi.fn()

describe('SSE 思考过程（推理链）事件解析', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockReset()
    window.localStorage.clear()
  })

  it('流式问答：解析 meta.trace、reasoning 增量与 done 兜底', async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        `event: meta\ndata: ${JSON.stringify({
          insufficient_evidence: false,
          sources: [],
          model: 'fake-model',
          trace,
        })}`,
        'event: reasoning\ndata: {"text":"先想想"}',
        'event: reasoning\ndata: {"text":"再想想"}',
        'event: delta\ndata: {"text":"答案"}',
        `event: done\ndata: ${JSON.stringify({
          answer: '答案',
          usage: null,
          latency_ms: 12,
          reasoning: '先想想再想想',
          reasoning_ms: 80,
        })}`,
      ]),
    )

    const onMeta = vi.fn()
    const onReasoning = vi.fn()
    const onDelta = vi.fn()

    const result = await streamChat(
      'mtg_1',
      { question: '决定了什么？' },
      { onMeta, onReasoning, onDelta },
    )

    expect(onMeta).toHaveBeenCalledTimes(1)
    expect(result.meta?.trace?.stages[0]?.detail).toBe('命中 1 条')
    expect(onReasoning.mock.calls.map(([text]) => text)).toEqual(['先想想', '再想想'])
    expect(result.reasoning).toBe('先想想再想想')
    expect(onDelta).toHaveBeenCalledWith('答案')
    expect(result.answer).toBe('答案')
  })

  it('Agent 单轮：解析 meta.trace 与 reasoning 事件', async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        `event: intent\ndata: ${JSON.stringify({
          intent: 'chat',
          confidence: 1,
          slots: {},
          needs_clarification: false,
          clarification_question: null,
          source: 'rule',
        })}`,
        `event: meta\ndata: ${JSON.stringify({
          sources: [{ meeting_id: 'mtg_1', material_id: null, record_id: null, excerpt: '片段' }],
          insufficient_evidence: false,
          trace,
        })}`,
        'event: reasoning\ndata: {"text":"先想想"}',
        'event: delta\ndata: {"text":"答案"}',
        `event: done\ndata: ${JSON.stringify({
          session_id: 'ags_1',
          intent: {
            intent: 'chat',
            confidence: 1,
            slots: {},
            needs_clarification: false,
            clarification_question: null,
            source: 'rule',
          },
          reply: { content: '答案', sources: [], reasoning: '先想想', reasoning_ms: 50 },
        })}`,
      ]),
    )

    const onMeta = vi.fn()
    const onReasoning = vi.fn()
    const onDelta = vi.fn()

    const done = await streamAgentTurn(
      { scene: 'minutes', message: '决定了什么？' },
      { onMeta, onReasoning, onDelta },
    )

    expect(onMeta.mock.calls[0][0].trace?.stages[1]?.id).toBe('generate')
    expect(onReasoning).toHaveBeenCalledWith('先想想')
    expect(onDelta).toHaveBeenCalledWith('答案')
    expect(done.reply.reasoning).toBe('先想想')
    expect(done.reply.reasoning_ms).toBe(50)
  })
})
