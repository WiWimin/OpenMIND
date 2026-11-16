import http from '@/api/client'
import { streamChat, type ChatStreamResult } from '@/api/chatStream'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess } from '@/types/api'
import type {
  ChatPayload,
  ChatResult,
  ChatStreamMeta,
  OrganizePayload,
  OrganizeResult,
} from '@/types/chat'
import { unwrapData } from '@/utils/apiEnvelope'

export async function askMeeting(
  meetingId: string,
  payload: ChatPayload,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const { data } = await http.post<ApiSuccess<ChatResult> | ChatResult>(
    `/meetings/${meetingId}/chat`,
    payload,
    { timeout: LONG_REQUEST_TIMEOUT_MS, ...(signal ? { signal } : {}) },
  )
  return unwrapData(data)
}

function isResourceNotFound(caught: unknown): boolean {
  return (
    typeof caught === 'object' &&
    caught !== null &&
    'error_code' in caught &&
    (caught as { error_code: unknown }).error_code === 'RESOURCE_NOT_FOUND'
  )
}

/**
 * 流式问答（SSE `POST /meetings/{id}/chat/stream`，api.md 5.7a）。
 *
 * - 增量经 `onDelta` 回调实时上抛，meta（来源/证据不足标记）经 `onMeta` 首帧下发；
 * - 模型原生推理经 `onReasoning` 上抛（思考过程），trace 见 `meta.trace`；
 * - 端点返回 404（`SSE_CHAT_ENABLED=false` 或会议不存在）时**回退同步 `askMeeting`**，
 *   由同步接口给出其自身的正确错误；
 * - 其余错误原样抛出（统一 ApiError）。
 */
export async function askMeetingStream(
  meetingId: string,
  payload: ChatPayload,
  handlers: {
    onMeta?: (meta: ChatStreamMeta) => void
    onDelta?: (text: string) => void
    onReasoning?: (text: string) => void
  } = {},
  signal?: AbortSignal,
): Promise<ChatResult> {
  let result: ChatStreamResult
  try {
    result = await streamChat(meetingId, payload, {
      signal,
      onMeta: handlers.onMeta,
      onDelta: handlers.onDelta,
      onReasoning: handlers.onReasoning,
    })
  } catch (caught) {
    if (isResourceNotFound(caught)) {
      return askMeeting(meetingId, payload, signal)
    }
    throw caught
  }
  return {
    answer: result.answer,
    sources: result.meta?.sources ?? [],
    insufficient_evidence: result.meta?.insufficient_evidence ?? false,
    file: null,
    reasoning: result.reasoning || undefined,
  }
}

export async function organizeRecords(
  meetingId: string,
  payload: OrganizePayload,
  signal?: AbortSignal,
): Promise<OrganizeResult> {
  const { data } = await http.post<ApiSuccess<OrganizeResult> | OrganizeResult>(
    `/meetings/${meetingId}/organize`,
    payload,
    { timeout: LONG_REQUEST_TIMEOUT_MS, ...(signal ? { signal } : {}) },
  )
  return unwrapData(data)
}
