import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AgentChat from '@/components/AgentChat.vue'
import type { AgentReply, AgentStreamHandlers } from '@/types/agent'

function mountChat(overrides: Record<string, unknown> = {}) {
  const onSend = vi.fn().mockResolvedValue('同步回复')
  const onSendStream = vi.fn()
  const wrapper = mount(AgentChat, {
    props: {
      agentName: 'AI 助手',
      onSend,
      onSendStream,
      ...overrides,
    },
  })
  return { wrapper, onSend, onSendStream }
}

async function send(wrapper: ReturnType<typeof mountChat>['wrapper'], text: string): Promise<void> {
  await wrapper.get('#agent-chat-input').setValue(text)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('AgentChat streaming (onSendStream)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders meta sources first, appends deltas without the typing animation', async () => {
    const deferred: { resolve: ((reply: AgentReply) => void) | null } = { resolve: null }
    const onSendStream = vi.fn(
      (_text: string, _signal: AbortSignal, handlers: AgentStreamHandlers) => {
        handlers.onMeta?.([{ label: '会议资料', detail: '原文片段' }])
        handlers.onDelta?.('这是流式输出的第一段正文')
        handlers.onDelta?.('，继续追加第二段。')
        return new Promise<AgentReply>((resolve) => {
          deferred.resolve = resolve
        })
      },
    )
    const { wrapper, onSend } = mountChat({ onSendStream })

    await send(wrapper, '总结一下')

    // meta 先于完成到达：来源在回复结束前已渲染
    expect(wrapper.find('.agent-source').exists()).toBe(true)
    expect(wrapper.text()).toContain('会议资料')
    // 增量直接写入正文（不走打字动画，长文本也立即完整）
    expect(wrapper.text()).toContain('这是流式输出的第一段正文，继续追加第二段。')
    expect(wrapper.text()).toContain('正在输入')
    expect(onSend).not.toHaveBeenCalled()

    deferred.resolve?.({
      content: '',
      note: '已结合会议资料生成。',
      sources: [{ label: '会议资料', detail: '原文片段' }],
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('已结合会议资料生成。')
    expect(wrapper.find('.agent-message__status').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('正在输入')
    expect(wrapper.find('.agent-message__body--error').exists()).toBe(false)
  })

  it('keeps partial streamed content and shows the failure in the status line', async () => {
    const onSendStream = vi.fn(
      async (_text: string, _signal: AbortSignal, handlers: AgentStreamHandlers) => {
        handlers.onDelta?.('已经流出的部分正文')
        throw new Error('模型服务超时')
      },
    )
    const { wrapper } = mountChat({ onSendStream })

    await send(wrapper, '继续写')

    expect(wrapper.text()).toContain('已经流出的部分正文')
    expect(wrapper.find('.agent-message__body--error').exists()).toBe(true)
    expect(wrapper.find('.agent-message__status').text()).toContain('模型服务超时')
    // 部分正文不被错误文案覆盖
    expect(wrapper.find('.agent-message__content').text()).not.toContain('生成失败')
  })

  it('fills the bubble with the error message when nothing was streamed', async () => {
    const onSendStream = vi.fn().mockRejectedValue(new Error('生成失败，请稍后重试'))
    const { wrapper } = mountChat({ onSendStream })

    await send(wrapper, '继续写')

    expect(wrapper.find('.agent-message__content').text()).toContain('生成失败，请稍后重试')
    expect(wrapper.find('.agent-message__body--error').exists()).toBe(true)
  })

  it('keeps partial content when the user stops generation', async () => {
    const onSendStream = vi.fn(
      (_text: string, signal: AbortSignal, handlers: AgentStreamHandlers) => {
        handlers.onDelta?.('流到一半的内容')
        return new Promise<AgentReply>((_resolve, reject) => {
          signal.addEventListener('abort', () => {
            const error = new Error('aborted')
            error.name = 'AbortError'
            reject(error)
          })
        })
      },
    )
    const { wrapper } = mountChat({ onSendStream })

    await send(wrapper, '写长一点')
    expect(wrapper.text()).toContain('流到一半的内容')

    await wrapper.get('.agent-composer__stop').trigger('click')
    await flushPromises()

    // 已流出的正文保留，停止语义由状态行承担
    expect(wrapper.find('.agent-message__content').text()).toContain('流到一半的内容')
    expect(wrapper.find('.agent-message__status').text()).toContain('输出已停止')
    expect(wrapper.find('.agent-message__body--error').exists()).toBe(false)
  })

  it('routes quick tasks through onTask instead of the stream handler', async () => {
    const onTask = vi.fn().mockResolvedValue({ content: '整理结果' })
    const onSendStream = vi.fn()
    const onSend = vi.fn()
    const { wrapper } = mountChat({
      onTask,
      onSend,
      onSendStream,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })

    await wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))?.trigger('click')
    await wrapper.get('#agent-chat-input').setValue('重点看排期')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(onTask).toHaveBeenCalledWith('summary', '重点看排期', expect.any(AbortSignal))
    expect(onSendStream).not.toHaveBeenCalled()
    expect(onSend).not.toHaveBeenCalled()
  })
})
