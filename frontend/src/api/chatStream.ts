import { apiBaseUrl } from '@/api/client'
import type { ApiError } from '@/types/api'
import type { ChatPayload, ChatStreamDone, ChatStreamMeta } from '@/types/chat'
import { getToken } from '@/utils/authToken'

/**
 * SSE 流式问答客户端（api.md 5.7a）：fetch + ReadableStream 手写解析，不引入新依赖。
 *
 * - 事件：`meta` → `delta`* → `done`；`event: error` 抛出统一 ApiError；
 * - 首增量前的错误是普通 JSON 错误体（HTTP 状态码 + error_code）；
 * - `: ping` 心跳注释行忽略；`signal` 取消（AbortController）会中断读取。
 */
export interface StreamChatHandlers {
  onMeta?: (meta: ChatStreamMeta) => void
  onDelta?: (text: string) => void
  onDone?: (done: ChatStreamDone) => void
  /** 取消信号：与同步问答的 AbortController 对接 */
  signal?: AbortSignal
}

/** 流式结束后的累计结果（meta 可能为 null，如服务端异常未发首帧） */
export interface ChatStreamResult {
  meta: ChatStreamMeta | null
  answer: string
}

const STATUS_ERROR_CODES: Record<number, string> = {
  400: 'VALIDATION_ERROR',
  401: 'AUTH_REQUIRED',
  403: 'PERMISSION_DENIED',
  404: 'RESOURCE_NOT_FOUND',
  422: 'VALIDATION_ERROR',
  429: 'RATE_LIMITED',
}

function fallbackError(status: number): ApiError {
  if (status === 401) {
    return {
      status: 'error',
      error_code: 'AUTH_REQUIRED',
      message: '登录状态已失效，请重新登录',
      retryable: false,
    }
  }
  const code = STATUS_ERROR_CODES[status] ?? 'INTERNAL_ERROR'
  return {
    status: 'error',
    error_code: code,
    message: status >= 500 ? '服务暂时不可用，请稍后重试' : '请求失败，请稍后重试',
    retryable: status >= 500 || status === 429,
  }
}

function toApiError(body: unknown, status: number): ApiError {
  if (body && typeof body === 'object' && 'error_code' in body) {
    const candidate = body as ApiError
    if (typeof candidate.error_code === 'string') {
      return { ...candidate, status: 'error' }
    }
  }
  return fallbackError(status)
}

/** 把 SSE 帧拆成事件名与数据（`data:` 多行以换行拼接；`: ping` 注释忽略） */
function parseFrame(frame: string): { event: string; data: string } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) {
      continue
    }
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).replace(/^ /, ''))
    }
  }
  if (dataLines.length === 0) {
    return null
  }
  return { event, data: dataLines.join('\n') }
}

function parseJson<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T
  } catch {
    return null
  }
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

  const reader = response.body?.getReader()
  if (!reader) {
    throw fallbackError(500)
  }
  const decoder = new TextDecoder()
  const result: ChatStreamResult = { meta: null, answer: '' }
  let buffer = ''
  let finished = false

  const handleFrame = (frame: string): boolean => {
    const parsed = parseFrame(frame)
    if (!parsed) {
      return false
    }
    if (parsed.event === 'meta') {
      const meta = parseJson<ChatStreamMeta>(parsed.data)
      if (meta) {
        result.meta = meta
        handlers.onMeta?.(meta)
      }
    } else if (parsed.event === 'delta') {
      const delta = parseJson<{ text: string }>(parsed.data)
      if (delta && typeof delta.text === 'string' && delta.text) {
        result.answer += delta.text
        handlers.onDelta?.(delta.text)
      }
    } else if (parsed.event === 'done') {
      const done = parseJson<ChatStreamDone>(parsed.data)
      if (done && typeof done.answer === 'string' && done.answer) {
        result.answer = done.answer
      }
      handlers.onDone?.(
        done ?? { answer: result.answer, usage: null, latency_ms: 0 },
      )
      return true
    } else if (parsed.event === 'error') {
      const error = parseJson<ApiError>(parsed.data)
      throw error ? { ...error, status: 'error' } : fallbackError(500)
    }
    return false
  }

  try {
    while (!finished) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1 && !finished) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        finished = handleFrame(frame)
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    if (!finished) {
      // 出错或中断：停止读取上游，尽快释放连接
      await reader.cancel().catch(() => undefined)
    }
  }

  if (!finished) {
    throw {
      status: 'error',
      error_code: 'NETWORK_ERROR',
      message: '连接中断，请重试',
      retryable: true,
    } satisfies ApiError
  }
  return result
}
