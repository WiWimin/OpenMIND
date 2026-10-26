import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from '@/api/chat'
import ChatPanel from '@/components/ChatPanel.vue'
import type { ChatResult } from '@/types/chat'

vi.mock('@/api/chat', () => ({
  askMeeting: vi.fn(),
  organizeRecords: vi.fn(),
}))

const result: ChatResult = {
  answer: '上次会议决定了使用 Vue 3。',
  sources: [{ meeting_id: 'mtg_1', material_id: 'mat_1', record_id: null, excerpt: '相关原文片段' }],
  insufficient_evidence: false,
}

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('requires a question', async () => {
    const wrapper = mount(ChatPanel, { props: { meetingId: 'mtg_1' } })
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('请输入问题')
    expect(chatApi.askMeeting).not.toHaveBeenCalled()
  })

  it('asks and renders the answer with sources', async () => {
    vi.mocked(chatApi.askMeeting).mockResolvedValue(result)
    const wrapper = mount(ChatPanel, { props: { meetingId: 'mtg_1' } })

    await wrapper.get('#chat-question').setValue('上次决定什么？')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(chatApi.askMeeting).toHaveBeenCalledWith('mtg_1', {
      question: '上次决定什么？',
      context_scope: 'current_meeting',
      include_sources: true,
    })
    expect(wrapper.text()).toContain('使用 Vue 3')
    expect(wrapper.text()).toContain('相关原文片段')
  })

  it('sends the selected context scope', async () => {
    vi.mocked(chatApi.askMeeting).mockResolvedValue(result)
    const wrapper = mount(ChatPanel, { props: { meetingId: 'mtg_1' } })

    await wrapper.get('#chat-scope').setValue('current_and_history')
    await wrapper.get('#chat-question').setValue('历史会议？')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(chatApi.askMeeting).toHaveBeenCalledWith('mtg_1', {
      question: '历史会议？',
      context_scope: 'current_and_history',
      include_sources: true,
    })
  })

  it('warns when evidence is insufficient', async () => {
    vi.mocked(chatApi.askMeeting).mockResolvedValue({ ...result, insufficient_evidence: true })
    const wrapper = mount(ChatPanel, { props: { meetingId: 'mtg_1' } })

    await wrapper.get('#chat-question').setValue('问题')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('证据不足')
  })

  it('refills the last question when asking again', async () => {
    vi.mocked(chatApi.askMeeting).mockResolvedValue(result)
    const wrapper = mount(ChatPanel, { props: { meetingId: 'mtg_1' } })

    const again = wrapper.findAll('button').find((button) => button.text() === '重新提问')
    expect(again?.attributes('disabled')).toBeDefined()

    await wrapper.get('#chat-question').setValue('上次决定什么？')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const refill = wrapper.findAll('button').find((button) => button.text() === '重新提问')
    await refill?.trigger('click')

    const textarea = wrapper.get('#chat-question').element as HTMLTextAreaElement
    expect(textarea.value).toBe('上次决定什么？')
  })

  it('shows an error when the request fails', async () => {
    vi.mocked(chatApi.askMeeting).mockRejectedValue({
      error_code: 'MODEL_TIMEOUT',
      message: '模型超时',
    })
    const wrapper = mount(ChatPanel, { props: { meetingId: 'mtg_1' } })

    await wrapper.get('#chat-question').setValue('问题')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('模型超时')
  })
})
