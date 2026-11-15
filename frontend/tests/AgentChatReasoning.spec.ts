import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as agentApi from '@/api/agent'
import AgentChat from '@/components/AgentChat.vue'
import type {
  AgentBackendMessage,
  AgentBackendSession,
  AgentReply,
  AgentStreamHandlers,
  ChatTrace,
} from '@/types/agent'

vi.mock('@/api/agent', () => ({
  ensureSession: vi.fn(),
  listMessages: vi.fn(),
  listPendingActions: vi.fn(),
  deleteSession: vi.fn(),
  approvePendingAction: vi.fn(),
  rejectPendingAction: vi.fn(),
  streamAgentTurn: vi.fn(),
}))

const trace: ChatTrace = {
  stages: [
    { id: 'intent', label: '理解问题', status: 'done', detail: '会议问答' },
    {
      id: 'retrieve',
      label: '检索会议资料',
      status: 'done',
      detail: '命中 2 条相关片段',
    },
    { id: 'generate', label: '生成回答', status: 'running' },
  ],
  native_reasoning: true,
}

/**
 * v-show 折叠状态：读内联 style 而不是 isVisible()。
 * jsdom 在「先读一次可见性、再取消 display:none」时会返回过期的 computed 值。
 */
function bodyHidden(wrapper: VueWrapper): boolean {
  const style = wrapper.find('.agent-reasoning__body').attributes('style')
  return (style ?? '').includes('display: none')
}

function mountChat(overrides: Record<string, unknown> = {}) {
  const onSend = vi.fn().mockResolvedValue('同步回复')
  const wrapper = mount(AgentChat, {
    props: {
      agentName: 'AI 助手',
      onSend,
      ...overrides,
    },
  })
  return { wrapper, onSend }
}

async function send(wrapper: ReturnType<typeof mountChat>['wrapper'], text: string): Promise<void> {
  await wrapper.get('#agent-chat-input').setValue(text)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

/** 只捕获回调、不立即产出的流式 handler（便于逐帧断言） */
function deferredStream() {
  let handlers: AgentStreamHandlers | undefined
  let resolveReply: ((reply: AgentReply) => void) | null = null
  const onSendStream = vi.fn(
    (_text: string, _signal: AbortSignal, captured: AgentStreamHandlers) => {
      handlers = captured
      return new Promise<AgentReply>((resolve) => {
        resolveReply = resolve
      })
    },
  )
  return {
    onSendStream,
    handlers: () => handlers,
    finish: (reply: AgentReply = { content: '' }) => {
      resolveReply?.(reply)
      return flushPromises()
    },
  }
}

const session: AgentBackendSession = {
  session_id: 'ags_1',
  user_id: 'usr_1',
  meeting_id: 'mtg_1',
  scene: 'minutes',
  title: null,
  status: 'active',
  created_at: '2026-11-16T10:00:00+08:00',
  updated_at: '2026-11-16T10:00:00+08:00',
}

const historyWithReasoning: AgentBackendMessage[] = [
  {
    message_id: 'agm_1',
    session_id: 'ags_1',
    role: 'assistant',
    content: '结论是本周五交付。',
    status: 'completed',
    created_at: '2026-11-16T10:02:00+08:00',
    meta: {
      reasoning: '先看材料里的项目排期。',
      reasoning_ms: 2500,
      trace: trace.stages,
    },
  },
]

describe('AgentChat 思考过程（推理链）', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.clearAllMocks()
  })

  it('渲染执行步骤与原生推理，正文开始后自动折叠', async () => {
    const stream = deferredStream()
    const { wrapper } = mountChat({ onSendStream: stream.onSendStream })

    await send(wrapper, '结论是什么')

    // 尚无 trace：不渲染面板
    expect(wrapper.find('.agent-reasoning').exists()).toBe(false)

    stream.handlers()?.onMeta?.([{ label: '会议资料' }], trace)
    stream.handlers()?.onReasoning?.('先看材料里的排期。')
    await flushPromises()

    const toggle = wrapper.get('.agent-reasoning__toggle')
    const body = wrapper.get('.agent-reasoning__body')
    // 生成中自动展开，aria-expanded 与区域 id 关联
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(toggle.attributes('aria-controls')).toBe(body.attributes('id'))
    expect(bodyHidden(wrapper)).toBe(false)
    expect(wrapper.text()).toContain('检索会议资料')
    expect(wrapper.text()).toContain('命中 2 条相关片段')
    expect(wrapper.text()).toContain('先看材料里的排期。')
    expect(wrapper.text()).toContain('思考中')

    // 首个正文增量到达 → 自动折叠，正文正常渲染
    stream.handlers()?.onDelta?.('结论是本周五交付。')
    await flushPromises()
    expect(wrapper.get('.agent-reasoning__toggle').attributes('aria-expanded')).toBe('false')
    expect(bodyHidden(wrapper)).toBe(true)
    expect(wrapper.find('.agent-message__content').text()).toContain('结论是本周五交付。')

    // 手动展开后保持展开（不再被自动折叠）
    await wrapper.get('.agent-reasoning__toggle').trigger('click')
    expect(wrapper.get('.agent-reasoning__toggle').attributes('aria-expanded')).toBe('true')
    expect(bodyHidden(wrapper)).toBe(false)

    await stream.finish({ content: '' })
    expect(wrapper.get('.agent-reasoning__toggle').attributes('aria-expanded')).toBe('true')
    expect(bodyHidden(wrapper)).toBe(false)
  })

  it('无原生推理时提示「实际执行步骤」', async () => {
    const stream = deferredStream()
    const { wrapper } = mountChat({ onSendStream: stream.onSendStream })

    await send(wrapper, '结论是什么')
    stream.handlers()?.onMeta?.([], { ...trace, native_reasoning: false })
    await flushPromises()

    expect(wrapper.find('.agent-reasoning').exists()).toBe(true)
    expect(wrapper.text()).toContain('当前模型未返回内部推理')
    // 没有推理文本时不渲染「模型推理」段
    expect(wrapper.find('.agent-reasoning__text').exists()).toBe(false)

    await stream.finish({ content: '正文' })
  })

  it('关闭思考开关后不请求思考、也不显示面板', async () => {
    const stream = deferredStream()
    const { wrapper } = mountChat({ onSendStream: stream.onSendStream })

    const toggle = wrapper.get('.agent-thinking-toggle')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    await toggle.trigger('click')
    expect(wrapper.get('.agent-thinking-toggle').attributes('aria-pressed')).toBe('false')

    await send(wrapper, '结论是什么')
    expect(stream.handlers()?.thinking).toBe(false)

    stream.handlers()?.onMeta?.([{ label: '会议资料' }], trace)
    stream.handlers()?.onReasoning?.('不该显示的推理')
    await flushPromises()

    expect(wrapper.find('.agent-reasoning').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('不该显示的推理')

    await stream.finish({ content: '正文' })
  })

  it('恢复的服务端历史默认折叠，可展开查看推理与耗时', async () => {
    vi.mocked(agentApi.ensureSession).mockResolvedValue(session)
    vi.mocked(agentApi.listMessages).mockResolvedValue(historyWithReasoning)
    vi.mocked(agentApi.listPendingActions).mockResolvedValue([])

    const { wrapper } = mountChat({
      backendSession: true,
      agentScene: 'minutes',
      meetingId: 'mtg_1',
      storageKey: 'minutes:mtg_1',
    })
    await flushPromises()

    const toggle = wrapper.get('.agent-reasoning__toggle')
    expect(wrapper.text()).toContain('结论是本周五交付。')
    expect(toggle.text()).toContain('已思考 2.5 秒')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(bodyHidden(wrapper)).toBe(true)

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(bodyHidden(wrapper)).toBe(false)
    expect(wrapper.text()).toContain('先看材料里的项目排期。')
  })

  it('后端流式：渲染 reasoning 与 trace，并把 thinking 透传给单轮', async () => {
    vi.mocked(agentApi.ensureSession).mockResolvedValue(session)
    vi.mocked(agentApi.listMessages).mockResolvedValue([])
    vi.mocked(agentApi.listPendingActions).mockResolvedValue([])
    vi.mocked(agentApi.streamAgentTurn).mockImplementation(async (_payload, handlers) => {
      handlers?.onMeta?.({ sources: [], trace })
      handlers?.onReasoning?.('先看材料里的排期。')
      handlers?.onDelta?.('结论是本周五交付。')
      return {
        session_id: 'ags_1',
        intent: {
          intent: 'chat',
          confidence: 1,
          slots: {},
          needs_clarification: false,
          clarification_question: null,
          source: 'explicit',
        },
        reply: {
          content: '结论是本周五交付。',
          sources: [],
          reasoning: '先看材料里的排期。',
          reasoning_ms: 1200,
          trace: trace.stages,
        },
        accepted: false,
      }
    })

    const { wrapper } = mountChat({
      backendSession: true,
      agentScene: 'minutes',
      meetingId: 'mtg_1',
      storageKey: 'minutes:mtg_1',
    })
    await flushPromises()

    await send(wrapper, '结论是什么')
    await flushPromises()

    const call = vi.mocked(agentApi.streamAgentTurn).mock.calls[0]
    expect(call[0].options?.thinking).toBe(true)
    expect(wrapper.text()).toContain('先看材料里的排期。')
    expect(wrapper.text()).toContain('命中 2 条相关片段')
    // 正文到达后面板自动折叠
    expect(wrapper.get('.agent-reasoning__toggle').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('.agent-reasoning__toggle').text()).toContain('已思考 1.2 秒')
  })
})
