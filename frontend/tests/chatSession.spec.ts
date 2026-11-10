import { beforeEach, describe, expect, it } from 'vitest'

import type { AgentChatMessage } from '@/types/agent'
import {
  buildChatStorageKey,
  clearChatSession,
  loadChatSession,
  saveChatSession,
} from '@/utils/chatSession'

function message(partial: Partial<AgentChatMessage> & { id: number; role: 'user' | 'assistant' }): AgentChatMessage {
  return {
    content: 'hello',
    streaming: false,
    createdAt: 1_700_000_000_000,
    ...partial,
  }
}

const KEY = buildChatStorageKey('preprocess', 'mtg_1')
const PREFIX = 'openmind:agent-chat:v1'

/** 实际存储键（工具内部会加项目前缀） */
function fullKey(key: string): string {
  return `${PREFIX}:${key}`
}

describe('chatSession', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('builds a scene-scoped key', () => {
    expect(buildChatStorageKey('asr', 'mtg_2')).toBe('asr:mtg_2')
  })

  it('round-trips messages and draft', () => {
    const messages = [
      message({ id: 1, role: 'user', content: '你好' }),
      message({ id: 2, role: 'assistant', content: '在' }),
    ]
    saveChatSession(KEY, { draft: '半句话', messages })

    const loaded = loadChatSession(KEY)
    expect(loaded).not.toBeNull()
    expect(loaded?.draft).toBe('半句话')
    expect(loaded?.messages).toHaveLength(2)
    expect(loaded?.messages[0].content).toBe('你好')
  })

  it('returns null for a missing or corrupted session', () => {
    expect(loadChatSession(buildChatStorageKey('preprocess', 'mtg_none'))).toBeNull()

    window.localStorage.setItem(fullKey(KEY), '{not json')
    expect(loadChatSession(KEY)).toBeNull()

    window.localStorage.setItem(fullKey(KEY), JSON.stringify({ v: 2, messages: [] }))
    expect(loadChatSession(KEY)).toBeNull()

    window.localStorage.setItem(fullKey(KEY), JSON.stringify({ v: 1, messages: 'oops' }))
    expect(loadChatSession(KEY)).toBeNull()
  })

  it('normalizes interrupted streaming messages on load', () => {
    window.localStorage.setItem(
      fullKey(KEY),
      JSON.stringify({
        v: 1,
        updatedAt: Date.now(),
        draft: '',
        messages: [
          message({ id: 1, role: 'user', content: '提问' }),
          // 中断的空回复：丢弃
          message({ id: 2, role: 'assistant', content: '', streaming: true }),
          // 中断但有内容：保留并落地
          message({ id: 3, role: 'assistant', content: '写到一半', streaming: true }),
          // 缺 id/时间：补齐
          { role: 'user', content: '补' },
        ],
      }),
    )

    const loaded = loadChatSession(KEY)
    expect(loaded?.messages).toHaveLength(3)
    expect(loaded?.messages.every((item) => !item.streaming)).toBe(true)
    expect(loaded?.messages[1].content).toBe('写到一半')
    expect(typeof loaded?.messages[2].id).toBe('number')
    expect(typeof loaded?.messages[2].createdAt).toBe('number')
  })

  it('drops malformed entries instead of failing the whole session', () => {
    window.localStorage.setItem(
      fullKey(KEY),
      JSON.stringify({
        v: 1,
        updatedAt: Date.now(),
        draft: '',
        messages: [message({ id: 1, role: 'user' }), { role: 'nope', content: 1 }, null, 42],
      }),
    )

    expect(loadChatSession(KEY)?.messages).toHaveLength(1)
  })

  it('clears the session', () => {
    saveChatSession(KEY, { draft: '', messages: [message({ id: 1, role: 'user' })] })
    clearChatSession(KEY)
    expect(loadChatSession(KEY)).toBeNull()
  })

  it('removes the archive when both messages and draft are empty', () => {
    saveChatSession(KEY, { draft: '', messages: [message({ id: 1, role: 'user' })] })
    saveChatSession(KEY, { draft: '   ', messages: [] })
    expect(loadChatSession(KEY)).toBeNull()
  })

  it('trims the oldest messages when over the size budget', () => {
    const big = 'x'.repeat(30 * 1024)
    const messages = Array.from({ length: 40 }, (_, index) =>
      message({ id: index + 1, role: 'user', content: `${index}-${big}` }),
    )
    saveChatSession(KEY, { draft: '', messages })

    const raw = window.localStorage.getItem(fullKey(KEY)) ?? ''
    expect(raw.length).toBeLessThan(400 * 1024)
    const loaded = loadChatSession(KEY)
    expect(loaded).not.toBeNull()
    expect(loaded!.messages.length).toBeLessThan(40)
    // 最新的保住了
    expect(loaded!.messages.at(-1)?.content.startsWith('39-')).toBe(true)
  })

  it('keeps only the most recent sessions per prefix (LRU)', () => {
    const now = Date.now()
    for (let i = 0; i < 35; i += 1) {
      const key = fullKey(buildChatStorageKey('preprocess', `mtg_${i}`))
      window.localStorage.setItem(
        key,
        JSON.stringify({
          v: 1,
          updatedAt: now - i * 1000,
          draft: '',
          messages: [message({ id: 1, role: 'user' })],
        }),
      )
    }
    saveChatSession(KEY, { draft: '', messages: [message({ id: 1, role: 'user' })] })

    const remaining = Object.keys(window.localStorage).filter((item) =>
      item.startsWith('openmind:agent-chat:v1:'),
    )
    expect(remaining.length).toBeLessThanOrEqual(30)
    // 当前会话一定在
    expect(remaining).toContain(fullKey(KEY))
  })
})
