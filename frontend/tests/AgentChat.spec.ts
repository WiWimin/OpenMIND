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

  it('shows a task chip instead of sending when a task quick action is clicked', async () => {
    const onSend = vi.fn()
    const onTask = vi.fn()
    const { wrapper } = mountChat({
      onSend,
      onTask,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })
    const starter = wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))

    await starter?.trigger('click')

    // 不立即发送，输入框挂上黄色任务标记
    expect(onTask).not.toHaveBeenCalled()
    expect(onSend).not.toHaveBeenCalled()
    expect(wrapper.find('.agent-task-chip').exists()).toBe(true)
    expect(wrapper.text()).toContain('#提炼要点')
  })

  it('sends the task with typed instruction after the chip is confirmed', async () => {
    const onSend = vi.fn()
    const onTask = vi.fn().mockResolvedValue({
      content: '',
      kind: 'summary',
      structured: {
        conclusion: ['确定 v2 上线时间'],
        key_discussions: [],
        action_items: [],
        open_questions: [],
      },
    })
    const { wrapper } = mountChat({
      onSend,
      onTask,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))?.trigger('click')

    await wrapper.get('#agent-chat-input').setValue('重点看排期问题')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(onTask).toHaveBeenCalledWith('summary', '重点看排期问题', expect.any(AbortSignal))
    expect(onSend).not.toHaveBeenCalled()
    // 用户消息显示任务标记 + 补充文字
    expect(wrapper.text()).toContain('#提炼要点 重点看排期问题')
    expect(wrapper.text()).toContain('结论与决议')
  })

  it('shows the parrot mascot on fresh empty input and hides it after typing or sending', async () => {
    const { wrapper, onSend } = mountChat()
    await flushPromises()

    // 对话未开始且输入为空：显示
    expect(wrapper.find('.agent-composer__mascot').exists()).toBe(true)

    // 开始输入：隐藏
    await wrapper.get('#agent-chat-input').setValue('写点什么')
    expect(wrapper.find('.agent-composer__mascot').exists()).toBe(false)

    // 清空输入：恢复显示
    await wrapper.get('#agent-chat-input').setValue('')
    expect(wrapper.find('.agent-composer__mascot').exists()).toBe(true)

    // 发送后隐藏（即使输入框被清空）
    await wrapper.get('#agent-chat-input').setValue('你好')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(onSend).toHaveBeenCalled()
    expect(wrapper.find('.agent-composer__mascot').exists()).toBe(false)
  })

  it('indents the first line while a task chip is mounted in the input', async () => {
    const onTask = vi.fn().mockResolvedValue({ content: '结果' })
    const { wrapper } = mountChat({
      onTask,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))?.trigger('click')

    // 芯片挂载后位于输入框内部（field 容器内），并推动首行文字
    const chip = wrapper.find('.agent-task-chip')
    expect(chip.exists()).toBe(true)
    expect(chip.classes()).toContain('agent-task-chip')
    const textarea = wrapper.get('#agent-chat-input').element as HTMLTextAreaElement
    expect(textarea.style.textIndent).toMatch(/^\d+px$/)

    // 移除芯片后首行缩进复位
    await wrapper.get('.agent-task-chip__remove').trigger('click')
    expect((wrapper.get('#agent-chat-input').element as HTMLTextAreaElement).style.textIndent).toBe('')
  })

  it('sends a task with empty input directly', async () => {
    const onTask = vi.fn().mockResolvedValue({ content: '整理结果' })
    const { wrapper } = mountChat({
      onTask,
      quickActions: [{ label: '会议记录', prompt: '整理提示词', task: 'organize' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('会议记录'))?.trigger('click')

    // 输入框为空也允许发送
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(onTask).toHaveBeenCalledWith('organize', '', expect.any(AbortSignal))
    expect(wrapper.text()).toContain('#会议记录')
    expect(wrapper.text()).toContain('整理结果')
  })

  it('removes the task chip via the remove button', async () => {
    const onTask = vi.fn()
    const { wrapper } = mountChat({
      onTask,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))?.trigger('click')
    expect(wrapper.find('.agent-task-chip').exists()).toBe(true)

    await wrapper.get('.agent-task-chip__remove').trigger('click')
    expect(wrapper.find('.agent-task-chip').exists()).toBe(false)

    await wrapper.get('form').trigger('submit')
    expect(onTask).not.toHaveBeenCalled()
  })

  it('clears the task chip with Escape', async () => {
    const onTask = vi.fn()
    const { wrapper } = mountChat({
      onTask,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))?.trigger('click')
    expect(wrapper.find('.agent-task-chip').exists()).toBe(true)

    await wrapper.get('#agent-chat-input').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.agent-task-chip').exists()).toBe(false)
  })

  it('routes plain quick actions without task through onSend', async () => {
    const onSend = vi.fn().mockResolvedValue('收到')
    const onTask = vi.fn()
    const { wrapper } = mountChat({
      onSend,
      onTask,
      quickActions: [{ label: '普通快捷', prompt: '普通提示词' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('普通快捷'))?.trigger('click')
    await flushPromises()

    expect(onSend).toHaveBeenCalledWith('普通提示词', expect.any(AbortSignal))
    expect(onTask).not.toHaveBeenCalled()
    expect(wrapper.find('.agent-task-chip').exists()).toBe(false)
  })

  it('mounts a prompt-mode chip via setPendingQuickAction and combines the designed prompt with typed text', async () => {
    const onSend = vi.fn().mockResolvedValue('整理结果')
    const onTask = vi.fn()
    const wrapper = mount(AgentChat, {
      props: { agentName: '预处理助手', onSend, onTask },
    })
    // 模拟资料预处理页气泡：外部挂载提示词模式标记
    const vm = wrapper.vm as unknown as {
      setPendingQuickAction: (action: { label: string; prompt: string }) => void
    }
    vm.setPendingQuickAction({ label: '会议摘要', prompt: '请生成会前准备摘要与准备清单。' })
    await flushPromises()

    expect(wrapper.find('.agent-task-chip').exists()).toBe(true)
    expect(wrapper.text()).toContain('#会议摘要')

    await wrapper.get('#agent-chat-input').setValue('重点列时间安排')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    // 设计好的完整提示词与用户补充自动组合后发送
    expect(onSend).toHaveBeenCalledWith(
      '请生成会前准备摘要与准备清单。\n\n用户补充：重点列时间安排',
      expect.any(AbortSignal),
    )
    expect(onTask).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('#会议摘要 重点列时间安排')
  })

  it('sends the designed prompt alone when the prompt-mode chip has no typed text', async () => {
    const onSend = vi.fn().mockResolvedValue('结果')
    const wrapper = mount(AgentChat, {
      props: { agentName: '预处理助手', onSend },
    })
    const vm = wrapper.vm as unknown as {
      setPendingQuickAction: (action: { label: string; prompt: string }) => void
    }
    vm.setPendingQuickAction({ label: '会议议程', prompt: '请基于已上传资料生成会议议程。' })
    await flushPromises()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(onSend).toHaveBeenCalledWith('请基于已上传资料生成会议议程。', expect.any(AbortSignal))
  })

  it('renders polish suggestions read-only by default', async () => {
    const onTask = vi.fn().mockResolvedValue({
      content: '',
      kind: 'polish',
      structured: [
        {
          location: '今天下午两',
          original: '今天下午两点的会一',
          suggested: '今天下午两点的会议',
          reason: '语音识别错误',
          confidence: 'high',
        },
      ],
    })
    const { wrapper } = mountChat({
      onTask,
      quickActions: [{ label: '修正口误', prompt: '修正提示词', task: 'polish' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('修正口误'))?.trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('今天下午两点的会一')
    expect(wrapper.text()).toContain('今天下午两点的会议')
    expect(wrapper.text()).toContain('语音识别错误')
    // 默认只读：无采纳按钮
    expect(wrapper.text()).not.toContain('采纳选中')
  })

  it('degrades to plain text when structured parse failed', async () => {
    const onTask = vi.fn().mockResolvedValue({
      content: '抱歉，我无法完成该任务。',
      kind: 'summary',
      structured: null,
    })
    const { wrapper } = mountChat({
      onTask,
      quickActions: [{ label: '提炼要点', prompt: '提炼提示词', task: 'summary' }],
    })
    await wrapper.findAll('button').find((button) => button.text().includes('提炼要点'))?.trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('抱歉，我无法完成该任务。')
    expect(wrapper.text()).not.toContain('结论与决议')
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
