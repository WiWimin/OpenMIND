import { apiBaseUrl } from '@/api/client'
import {
  fallbackError,
  interruptedError,
  parseJson,
  readSse,
  toApiError,
} from '@/api/sse'
import type { ApiError } from '@/types/api'
import type { ChatPayload, ChatStreamDone, ChatStreamMeta } from '@/types/chat'
import { getToken } from '@/utils/authToken'

/**
 * SSE 流式问答客户端（api.md 5.7a）：fetch + ReadableStream 手写解析，不引入新依赖。
 *
 * - 事件：`meta` → `reasoning`* / `delta`* → `done`；`event: error` 抛出统一 ApiError；
 * - 首增量前的错误是普通 JSON 错误体（HTTP 状态码 + error_code）；
 * - `: ping` 心跳注释行忽略；`signal` 取消（AbortController）会中断读取。
 */
export interface StreamChatHandlers {
  onMeta?: (meta: ChatStreamMeta) => void
  onDelta?: (text: string) => void
  /** 模型原生推理增量（思考过程） */
  onReasoning?: (text: string) => void
  onDone?: (done: ChatStreamDone) => void
  /** 取消信号：与同步问答的 AbortController 对接 */
  signal?: AbortSignal
}

/** 流式结束后的累计结果（meta 可能为 null，如服务端异常未发首帧） */
export interface ChatStreamResult {
  meta: ChatStreamMeta | null
  answer: string
  /** 累计的原生推理（思考过程） */
  reasoning: string
}

/**
 * 发起流式问答并逐帧回调。返回累计 meta 与回答文本。
 * 任何错误（HTTP 错误体 / `event: error` / 流中断）都以 ApiError 抛出。
 */
export async function streamChat(
  meetingId: string,
  payload: ChatPayload,
  handlers: StreamChatHandlers = {},
): Promise<ChatStreamResult> {
  const token = getToken()
  const response = await fetch(`${apiBaseUrl}/meetings/${meetingId}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    ...(handlers.signal ? { signal: handlers.signal } : {}),
  })

  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      // 非 JSON 错误体（如代理返回的 HTML），走状态码兜底
    }
    throw toApiError(body, response.status)
  }

  const result: ChatStreamResult = { meta: null, answer: '', reasoning: '' }

  const finished = await readSse(response, (event, data) => {
    if (event === 'meta') {
      const meta = parseJson<ChatStreamMeta>(data)
      if (meta) {
        result.meta = meta
        handlers.onMeta?.(meta)
      }
    } else if (event === 'reasoning') {
      const chunk = parseJson<{ text?: string }>(data)
      if (chunk && typeof chunk.text === 'string' && chunk.text) {
        result.reasoning += chunk.text
        handlers.onReasoning?.(chunk.text)
      }
    } else if (event === 'delta') {
      const delta = parseJson<{ text: string }>(data)
      if (delta && typeof delta.text === 'string' && delta.text) {
        result.answer += delta.text
        handlers.onDelta?.(delta.text)
      }
    } else if (event === 'done') {
      const done = parseJson<ChatStreamDone>(data)
      if (done && typeof done.answer === 'string' && done.answer) {
        result.answer = done.answer
      }
      if (done && typeof done.reasoning === 'string' && done.reasoning) {
        // 服务端给出完整推理：覆盖增量累计，兜底增量丢失的情况
        result.reasoning = done.reasoning
      }
      handlers.onDone?.(
        done ?? { answer: result.answer, usage: null, latency_ms: 0 },
      )
      return true
    } else if (event === 'error') {
      const error = parseJson<ApiError>(data)
      throw error ? { ...error, status: 'error' } : fallbackError(500)
    }
    return false
  })

  if (!finished) {
    throw interruptedError()
  }
  return result
}
