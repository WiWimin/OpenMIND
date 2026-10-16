import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from '@/api/chat'
import * as minutesApi from '@/api/minutes'
import AiAssistantDrawer from '@/components/AiAssistantDrawer.vue'
import type { Minutes } from '@/types/minutes'

vi.mock('@/api/chat', () => ({
  askMeeting: vi.fn(),
  organizeRecords: vi.fn(),
}))

vi.mock('@/api/minutes', () => ({
  listMinutes: vi.fn(),
  generateMinutes: vi.fn(),
  getMinutes: vi.fn(),
  updateMinutes: vi.fn(),
  confirmMinutes: vi.fn(),
}))

const minutes: Minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: 'AI 生成的草稿内容',
  status: 'draft',
  version: 1,
  source_record_ids: [],
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
}

function mountDrawer() {
  return mount(AiAssistantDrawer, {
    props: { open: true, meetingId: 'mtg_1' },
  })
}

async function submitQuestion(wrapper: ReturnType<typeof mount>, text: string) {
  await wrapper.get('#ai-drawer-question').setValue(text)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('AiAssistantDrawer', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders nothing while closed', () => {
    const wrapper = mount(AiAssistantDrawer, {
      props: { open: false, meetingId: 'mtg_1' },
    })
    expect(wrapper.find('.ai-drawer').exists()).toBe(false)
  })

  it('asks the meeting chat and shows the answer', async () => {
    vi.mocked(chatApi.askMeeting).mockResolvedValue({
      answer: '材料里提到第三季度目标已完成。',
      sources: [
        {
          meeting_id: 'mtg_1',
          material_id: 'mat_1',
          record_id: null,
          excerpt: '第三季度目标已完成。',
        },
      ],
      insufficient_evidence: false,
    })
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '第三季度目标完成了吗')

    expect(chatApi.askMeeting).toHaveBeenCalledWith('mtg_1', {
      question: '第三季度目标完成了吗',
      include_sources: true,
    })
    expect(wrapper.text()).toContain('材料里提到第三季度目标已完成。')
    expect(wrapper.text()).toContain('来源')
  })

  it('opens an editable draft panel when the user asks to generate minutes', async () => {
    vi.mocked(minutesApi.generateMinutes).mockResolvedValue(minutes)
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '帮我生成一下会议纪要')

    expect(minutesApi.generateMinutes).toHaveBeenCalledWith('mtg_1', {
      record_ids: [],
      include_action_items: true,
    })
    expect(chatApi.askMeeting).not.toHaveBeenCalled()
    const result = wrapper.get('#ai-drawer-result').element as HTMLTextAreaElement
    expect(result.value).toBe('AI 生成的草稿内容')
    expect(wrapper.text()).toContain('AI 生成的纪要草稿')
  })

  it('generates minutes from the capability chip', async () => {
    vi.mocked(minutesApi.generateMinutes).mockResolvedValue(minutes)
    const wrapper = mountDrawer()

    await wrapper
      .findAll('button')
      .find((button) => button.text() === '生成会议纪要')
      ?.trigger('click')
    await flushPromises()

    expect(minutesApi.generateMinutes).toHaveBeenCalled()
    expect(wrapper.find('.modal').exists()).toBe(true)
  })

  it('saves the edited draft and emits minutes-saved', async () => {
    vi.mocked(minutesApi.generateMinutes).mockResolvedValue(minutes)
    vi.mocked(minutesApi.updateMinutes).mockResolvedValue({
      ...minutes,
      content: '用户修改后的内容',
      version: 2,
    })
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '帮我生成一下会议纪要')
    await wrapper.get('#ai-drawer-result').setValue('用户修改后的内容')
    await wrapper
      .findAll('.modal button')
      .find((button) => button.text() === '保存草稿')
      ?.trigger('click')
    await flushPromises()

    expect(minutesApi.updateMinutes).toHaveBeenCalledWith('min_1', {
      content: '用户修改后的内容',
    })
    expect(wrapper.emitted('minutes-saved')).toHaveLength(1)
    expect(wrapper.find('.modal').exists()).toBe(false)
  })

  it('closes when the close button is clicked', async () => {
    const wrapper = mountDrawer()
    await wrapper.get('.ai-drawer__close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('navigates to the records tab with a guide when asked to organize', async () => {
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '帮我整理一下讨论记录')

    expect(chatApi.askMeeting).not.toHaveBeenCalled()
    expect(wrapper.emitted('navigate')?.[0]).toEqual(['records'])
    expect(wrapper.text()).toContain('AI 整理所选')
  })

  it('navigates to the issues tab with a guide when asked about open questions', async () => {
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '有哪些待确认问题')

    expect(wrapper.emitted('navigate')?.[0]).toEqual(['issues'])
    expect(wrapper.text()).toContain('提取问题')
  })

  it('navigates to the materials tab when asked about uploading documents', async () => {
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '在哪里上传会议材料')

    expect(wrapper.emitted('navigate')?.[0]).toEqual(['materials'])
    expect(wrapper.text()).toContain('「材料」小节')
  })

  it('still asks the chat for ordinary questions', async () => {
    vi.mocked(chatApi.askMeeting).mockResolvedValue({
      answer: '目标已完成。',
      sources: [],
      insufficient_evidence: false,
    })
    const wrapper = mountDrawer()

    await submitQuestion(wrapper, '第三季度目标完成了吗')

    expect(wrapper.emitted('navigate')).toBeUndefined()
    expect(chatApi.askMeeting).toHaveBeenCalled()
  })
})
