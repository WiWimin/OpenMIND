import http, { apiBaseUrl } from '@/api/client'
import {
  fallbackError,
  interruptedError,
  parseJson,
  readSse,
  toApiError,
} from '@/api/sse'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiError, ApiSuccess, ListData } from '@/types/api'
import type {
  AgentBackendMessage,
  AgentBackendSession,
  AgentBackendStreamHandlers,
  AgentPendingAction,
  AgentRun,
  AgentScene,
  AgentStreamDone,
  AgentTurnOptions,
  AgentTurnResponse,
  ChatTrace,
} from '@/types/agent'
import { getToken } from '@/utils/authToken'
import { unwrapData, unwrapList } from '@/utils/apiEnvelope'

/**
 * Agent 框架客户端（api.md 5.13）：服务端会话、消息、确认门与 SSE 单轮。
 *
 * 后端 `AGENT_ENABLED=false` 时接口返回 404（`RESOURCE_NOT_FOUND`），
 * 调用方据此回退既有页面链路。
 */

const AGENT = '/agent'

/** 按 `user + scene + meeting` 查找或创建默认会话（幂等） */
export async function ensureSession(payload: {
  scene: AgentScene
  meeting_id?: string
  title?: string
}): Promise<AgentBackendSession> {
  const { data } = await http.post<ApiSuccess<AgentBackendSession>>(
    `${AGENT}/sessions/ensure`,
    payload,
  )
  return unwrapData(data)
}

export async function listSessions(params: {
  scene?: AgentScene
  meeting_id?: string
  page?: number
  page_size?: number
}): Promise<AgentBackendSession[]> {
  const { data } = await http.get<ApiSuccess<ListData<AgentBackendSession>>>(
    `${AGENT}/sessions`,
    { params },
  )
  return unwrapList(data)
}

export async function listMessages(
  sessionId: string,
  params: { page?: number; page_size?: number } = {},
): Promise<AgentBackendMessage[]> {
  const { data } = await http.get<ApiSuccess<ListData<AgentBackendMessage>>>(
    `${AGENT}/sessions/${sessionId}/messages`,
    { params: { page: 1, page_size: 100, ...params } },
  )
  return unwrapList(data)
}

export async function listPendingActions(
  sessionId: string,
  status = 'pending',
): Promise<AgentPendingAction[]> {
  const { data } = await http.get<ApiSuccess<AgentPendingAction[]>>(
    `${AGENT}/sessions/${sessionId}/pending-actions`,
    { params: { status } },
  )
  return unwrapData(data) ?? []
}

export async function deleteSession(sessionId: string): Promise<void> {
  await http.delete(`${AGENT}/sessions/${sessionId}`)
}

/** 确认门：批准后工作流继续执行（如联网检索），返回最新一轮结果 */
export async function approvePendingAction(
  actionId: string,
  note?: string,
): Promise<AgentTurnResponse> {
  const { data } = await http.post<ApiSuccess<AgentTurnResponse>>(
    `${AGENT}/pending-actions/${actionId}/approve`,
    { note: note ?? null },
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  return unwrapData(data)
}

/** 确认门：拒绝后工作流以取消收尾，不产生副作用 */
export async function rejectPendingAction(
  actionId: string,
  note?: string,
): Promise<AgentTurnResponse> {
  const { data } = await http.post<ApiSuccess<AgentTurnResponse>>(
    `${AGENT}/pending-actions/${actionId}/reject`,
    { note: note ?? null },
  )
  return unwrapData(data)
}

export async function getRun(runId: string): Promise<AgentRun> {
  const { data } = await http.get<ApiSuccess<AgentRun>>(`${AGENT}/runs/${runId}`)
  return unwrapData(data)
}

export async function cancelRun(runId: string): Promise<AgentRun> {
  const { data } = await http.post<ApiSuccess<AgentRun>>(
    `${AGENT}/runs/${runId}/cancel`,
  )
  return unwrapData(data)
}

/**
 * 单轮流式对话（SSE `POST /agent/turns/stream`）。
 *
 * 事件：`intent` → `meta` → `reasoning`* / `delta`* → `pending_action`/`run` → `done`；
 * `event: error` 或首帧前 HTTP 错误统一以 ApiError 抛出。
 */
export async function streamAgentTurn(
  payload: {
    session_id?: string
    meeting_id?: string
    scene?: AgentScene
    message: string
    intent?: string
    options?: AgentTurnOptions
  },
  handlers: AgentBackendStreamHandlers = {},
): Promise<AgentStreamDone> {
  const token = getToken()
  const response = await fetch(`${apiBaseUrl}${AGENT}/turns/stream`, {
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

  let done: AgentStreamDone | null = null

  const finished = await readSse(response, (event, data) => {
    if (event === 'intent') {
      const intent = parseJson<AgentStreamDone['intent']>(data)
      if (intent) {
        handlers.onIntent?.(intent)
      }
    } else if (event === 'meta') {
      const meta = parseJson<{
        sources?: AgentStreamDone['reply']['sources']
        trace?: ChatTrace
      }>(data)
      handlers.onMeta?.({ sources: meta?.sources ?? [], trace: meta?.trace })
    } else if (event === 'reasoning') {
      const chunk = parseJson<{ text?: string }>(data)
      if (chunk && typeof chunk.text === 'string' && chunk.text) {
        handlers.onReasoning?.(chunk.text)
      }
    } else if (event === 'delta') {
      const delta = parseJson<{ text?: string }>(data)
      if (delta && typeof delta.text === 'string' && delta.text) {
        handlers.onDelta?.(delta.text)
      }
    } else if (event === 'pending_action') {
      const action = parseJson<AgentPendingAction>(data)
      if (action) {
        handlers.onPendingAction?.(action)
      }
    } else if (event === 'run') {
      const run = parseJson<AgentRun>(data)
      if (run) {
        handlers.onRun?.(run)
      }
    } else if (event === 'done') {
      const parsed = parseJson<AgentStreamDone>(data)
      if (parsed) {
        done = parsed
        handlers.onDone?.(parsed)
      }
      return true
    } else if (event === 'error') {
      const error = parseJson<ApiError>(data)
      throw error ? { ...error, status: 'error' } : fallbackError(500)
    }
    return false
  })

  if (!finished || done === null) {
    throw interruptedError()
  }
  return done
}
