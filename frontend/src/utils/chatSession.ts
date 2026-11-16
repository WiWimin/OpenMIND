import type { AgentChatMessage } from '@/types/agent'

/**
 * AI 对话本地持久化（localStorage）。
 *
 * 三阶段页（资料预处理 / 录音转写 / 会后智能处理）的 AgentChat 按
 * `scene + meetingId` 隔离保存，切页、刷新、重开浏览器后恢复；
 * 不传 storageKey 的用法保持原纯内存行为。
 */

const PREFIX = 'openmind:agent-chat:v1'
/** 单会话序列化上限（字节），超出从最旧消息开始裁剪 */
const MAX_SESSION_BYTES = 400 * 1024
/** 同前缀最多保留的会话数（按 updatedAt 做 LRU 清理） */
const MAX_SESSIONS = 30

interface ChatSessionPayload {
  v: 1
  updatedAt: number
  draft: string
  messages: AgentChatMessage[]
}

/** 会话键（如 `preprocess:mtg_1`）；实际存储键统一加项目前缀 */
export function buildChatStorageKey(scene: string, meetingId: string): string {
  return `${scene}:${meetingId}`
}

function fullKey(key: string): string {
  return `${PREFIX}:${key}`
}

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    // 隐私模式/禁用存储时降级为纯内存
    return null
  }
}

/** 归一化：流式占位一律落地，避免恢复后卡在「正在输入」 */
function normalize(messages: unknown): AgentChatMessage[] | null {
  if (!Array.isArray(messages)) {
    return null
  }
  const result: AgentChatMessage[] = []
  for (const item of messages) {
    if (typeof item !== 'object' || item === null) {
      continue
    }
    const candidate = item as Partial<AgentChatMessage>
    if (
      (candidate.role !== 'user' && candidate.role !== 'assistant') ||
      typeof candidate.content !== 'string'
    ) {
      continue
    }
    const message = candidate as AgentChatMessage
    if (message.streaming) {
      message.streaming = false
      // 中断的空回复不保留；有部分内容则保留并去掉输入态
      if (!message.content.trim() && message.role === 'assistant') {
        continue
      }
    }
    if (message.role === 'assistant') {
      // 恢复的历史消息：思考过程默认折叠并视为已完成
      message.reasoningOpen = false
      message.reasoningPinned = false
      message.reasoningDone = true
    }
    if (typeof message.id !== 'number' || !Number.isFinite(message.id)) {
      message.id = result.length + 1
    }
    if (typeof message.createdAt !== 'number' || !Number.isFinite(message.createdAt)) {
      message.createdAt = Date.now()
    }
    result.push(message)
  }
  return result
}

/** 载荷体积超限时从最旧消息裁剪，直到低于上限（至少保留最后一条） */
function trimToBudget(payload: ChatSessionPayload): ChatSessionPayload {
  if (byteLength(payload) <= MAX_SESSION_BYTES) {
    return payload
  }
  const messages = [...payload.messages]
  while (messages.length > 1 && byteLength({ ...payload, messages }) > MAX_SESSION_BYTES) {
    messages.shift()
  }
  return { ...payload, messages }
}

function byteLength(payload: ChatSessionPayload): number {
  try {
    return new TextEncoder().encode(JSON.stringify(payload)).length
  } catch {
    return 0
  }
}

function write(key: string, payload: ChatSessionPayload): void {
  const store = storage()
  if (!store) {
    return
  }
  const trimmed = trimToBudget(payload)
  try {
    store.setItem(fullKey(key), JSON.stringify(trimmed))
  } catch {
    // 配额仍满（其他站点数据占用）：裁半重试一次，再失败则放弃写入
    try {
      const half = { ...trimmed, messages: trimmed.messages.slice(-Math.ceil(trimmed.messages.length / 2)) }
      store.setItem(fullKey(key), JSON.stringify(half))
    } catch {
      /* 降级为内存态，不影响功能 */
    }
  }
}

/** LRU：同前缀会话按 updatedAt 保留最近 MAX_SESSIONS 个 */
function prune(key: string): void {
  const store = storage()
  if (!store) {
    return
  }
  const prefix = `${PREFIX}:`
  const self = fullKey(key)
  try {
    const entries: { key: string; updatedAt: number }[] = []
    for (let i = 0; i < store.length; i += 1) {
      const candidate = store.key(i)
      if (!candidate || !candidate.startsWith(prefix) || candidate === self) {
        continue
      }
      const raw = store.getItem(candidate)
      if (!raw) {
        continue
      }
      const parsed = JSON.parse(raw) as { updatedAt?: number }
      entries.push({ key: candidate, updatedAt: typeof parsed.updatedAt === 'number' ? parsed.updatedAt : 0 })
    }
    if (entries.length < MAX_SESSIONS) {
      return
    }
    entries.sort((a, b) => b.updatedAt - a.updatedAt)
    for (const stale of entries.slice(MAX_SESSIONS - 1)) {
      store.removeItem(stale.key)
    }
  } catch {
    /* 解析失败的脏数据不影响主流程 */
  }
}

/** 恢复会话；不存在或损坏返回 null */
export function loadChatSession(key: string): { draft: string; messages: AgentChatMessage[] } | null {
  const store = storage()
  if (!store || !key) {
    return null
  }
  const raw = store.getItem(fullKey(key))
  if (!raw) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ChatSessionPayload>
    if (parsed.v !== 1) {
      return null
    }
    const messages = normalize(parsed.messages)
    if (messages === null) {
      return null
    }
    return { draft: typeof parsed.draft === 'string' ? parsed.draft : '', messages }
  } catch {
    return null
  }
}

export function saveChatSession(
  key: string,
  data: { draft: string; messages: AgentChatMessage[] },
): void {
  if (!key) {
    return
  }
  // 对话与草稿都为空等价于清空，直接删除存档
  if (data.messages.length === 0 && !data.draft.trim()) {
    clearChatSession(key)
    return
  }
  const payload: ChatSessionPayload = {
    v: 1,
    updatedAt: Date.now(),
    draft: data.draft,
    messages: data.messages,
  }
  write(key, payload)
  prune(key)
}

export function clearChatSession(key: string): void {
  const store = storage()
  if (!store || !key) {
    return
  }
  store.removeItem(fullKey(key))
}
