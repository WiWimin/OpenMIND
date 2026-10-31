import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AgentChat from '@/components/AgentChat.vue'

function mountChat(overrides: Record<string, unknown> = {}) {
  const onSend = vi.fn().mockResolvedValue('收到，已结合会议资料处理。')
  const wrapper = mount(AgentChat, {
    props: {
      agentName: '会前处理',
      greeting: '你好，我是会前处理 Agent。',
      quickActions: [{ label: '提炼议题', prompt: '请提炼会议议题。' }],
      onSend,
      ...overrides,
    },
  })
  return { wrapper, onSend }
}

describe('AgentChat', () => {
  it('renders the greeting and streams a reply', async () => {
    const { wrapper, onSend } = mountChat()
    await flushPromises()

    expect(wrapper.text()).toContain('你好，我是会前处理 Agent。')

    await wrapper.get('#agent-chat-input').setValue('帮我提炼议题')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(onSend).toHaveBeenCalledWith('帮我提炼议题', expect.any(AbortSignal))
    expect(wrapper.text()).toContain('帮我提炼议题')
    expect(wrapper.text()).toContain('收到，已结合会议资料处理。')
  })

  it('renders a long streamed reply to completion', async () => {
    const longReply = `## 会议要点\n\n${'这是用于验证流式渲染的长文本。'.repeat(6)}`
    const onSend = vi.fn().mockResolvedValue(longReply)
    const { wrapper } = mountChat({ onSend })

    await wrapper.get('#agent-chat-input').setValue('生成长回复')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 3500))
    await flushPromises()

    expect(wrapper.text()).toContain('这是用于验证流式渲染的长文本。')
    expect(wrapper.text()).not.toContain('正在输入')
  })

  it('sends quick actions through the same handler', async () => {
    const { wrapper, onSend } = mountChat()
    const starter = wrapper.findAll('button').find((button) => button.text().includes('提炼议题'))

    await starter?.trigger('click')
    await flushPromises()

    expect(onSend).toHaveBeenCalledWith('请提炼会议议题。', expect.any(AbortSignal))
  })

  it('appends selected context to the question', async () => {
    const { wrapper, onSend } = mountChat({ contextText: '参会人 A：确定版本迭代时间' })

    await wrapper.get('#agent-chat-input').setValue('这句话是什么意思？')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(onSend).toHaveBeenCalledWith(
      '这句话是什么意思？\n\n【引用选中内容】\n参会人 A：确定版本迭代时间',
      expect.any(AbortSignal),
    )
    expect(wrapper.emitted('clear-context')).toHaveLength(1)
  })

  it('shows an inline error when the agent request fails', async () => {
    const onSend = vi.fn().mockRejectedValue(new Error('模型调用失败'))
    const { wrapper } = mountChat({ onSend })

    await wrapper.get('#agent-chat-input').setValue('生成纪要')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('模型调用失败')
  })

  it('sends with Enter and keeps Shift+Enter for new lines', async () => {
    const { wrapper, onSend } = mountChat()
    const input = wrapper.get('#agent-chat-input')
    await input.setValue('分析风险')

    await input.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()

    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(onSend).toHaveBeenCalledWith('分析风险', expect.any(AbortSignal))
  })

  it('aborts the in-flight request when stopped', async () => {
    let aborted = false
    const onSend = vi.fn(
      (_text: string, signal: AbortSignal) =>
        new Promise<string>((_resolve, reject) => {
          signal.addEventListener('abort', () => {
            aborted = true
            reject(new Error('aborted'))
          })
        }),
    )
    const { wrapper } = mountChat({ onSend })

    await wrapper.get('#agent-chat-input').setValue('生成一份很长的纪要')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const stop = wrapper.find('button[aria-label="停止生成"]')
    await stop.trigger('click')
    await flushPromises()

    expect(aborted).toBe(true)
    expect(wrapper.text()).toContain('已停止生成。')
  })
})
