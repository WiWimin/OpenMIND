import type { ApiError } from '@/types/api'

/**
 * SSE 客户端公共件：帧解析、错误归一与流读取。
 *
 * 供 `chatStream.ts`（会议问答）与 `agent.ts`（Agent 单轮）复用，
 * 避免两处各写一份 `ReadableStream` 解析逻辑。
 */

const STATUS_ERROR_CODES: Record<number, string> = {
  400: 'VALIDATION_ERROR',
  401: 'AUTH_REQUIRED',
  403: 'PERMISSION_DENIED',
  404: 'RESOURCE_NOT_FOUND',
  422: 'VALIDATION_ERROR',
  429: 'RATE_LIMITED',
}

export function fallbackError(status: number): ApiError {
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

export function toApiError(body: unknown, status: number): ApiError {
  if (body && typeof body === 'object' && 'error_code' in body) {
    const candidate = body as ApiError
    if (typeof candidate.error_code === 'string') {
      return { ...candidate, status: 'error' }
    }
  }
  return fallbackError(status)
}

/** 流中断（连接提前结束）统一错误体 */
export function interruptedError(): ApiError {
  return {
    status: 'error',
    error_code: 'NETWORK_ERROR',
    message: '连接中断，请重试',
    retryable: true,
  }
}

/** 把 SSE 帧拆成事件名与数据（`data:` 多行以换行拼接；`: ping` 注释忽略） */
export function parseFrame(frame: string): { event: string; data: string } | null {
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

export function parseJson<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T
  } catch {
    return null
  }
}

/**
 * 读取 SSE 响应体并逐帧回调。
 *
 * 回调返回 `true` 表示流结束（通常收到 `done`）；读取中断或异常时停止上游读取。
 * 返回 `true` 表示正常结束，`false` 表示连接提前断开。
 */
export async function readSse(
  response: Response,
  handle: (event: string, data: string) => boolean,
): Promise<boolean> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw fallbackError(500)
  }
  const decoder = new TextDecoder()
  let buffer = ''
  let finished = false

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
        const parsed = parseFrame(frame)
        if (parsed) {
          finished = handle(parsed.event, parsed.data)
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    if (!finished) {
      // 出错或中断：停止读取上游，尽快释放连接
      await reader.cancel().catch(() => undefined)
    }
  }
  return finished
}
