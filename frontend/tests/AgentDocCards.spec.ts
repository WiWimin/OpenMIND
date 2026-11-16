import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as materialsApi from '@/api/materials'
import AgentActionItemsCard from '@/components/AgentActionItemsCard.vue'
import AgentChat from '@/components/AgentChat.vue'
import AgentDocCard from '@/components/AgentDocCard.vue'
import type { AgentReply } from '@/types/agent'
import * as minutesDocx from '@/utils/minutesDocx'

const mirrorMeetingFile = vi.fn(async (): Promise<string> => 'written')
const downloadBlob = vi.fn()

vi.mock('@/api/materials', () => ({
  uploadMaterial: vi.fn(),
}))

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({ mirrorMeetingFile }),
}))

vi.mock('@/utils/minutesDocx', () => ({
  buildMinutesDocxBlob: vi.fn(async () => new Blob(['docx-bytes'])),
  downloadBlob: (blob: Blob, name: string) => downloadBlob(blob, name),
}))

vi.mock('@/utils/markdown', () => ({
  renderMarkdown: (source: string) => `<p>${source}</p>`,
}))

const minutesFile = { filename: '周会-纪要-v1.md', content: '# 结论\n\n- 完成灰度检查' }
const minutesMeta = {
  minutes_id: 'min_1',
  version: 1,
  status: 'draft',
  template: 'standard',
  title: '项目周会',
}

const actionItems = [
  {
    action_id: 'act_1',
    content: '完成灰度发布检查清单',
    assignee: '李雷',
    due_date: '2026-11-21',
    status: 'pending_confirmation',
  },
  { action_id: 'act_2', content: '确认模型额度', assignee: null, due_date: null, status: 'pending_confirmation' },
]

function mountChat(reply: AgentReply, overrides: Record<string, unknown> = {}) {
  const onSend = vi.fn().mockResolvedValue(reply)
  const wrapper = mount(AgentChat, {
    props: {
      agentName: '会后处理',
      meetingId: 'mtg_1',
      onSend,
      ...overrides,
    },
  })
  return { wrapper, onSend }
}

async function send(wrapper: ReturnType<typeof mount>, text: string) {
  await wrapper.get('#agent-chat-input').setValue(text)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('AgentDocCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(minutesDocx.buildMinutesDocxBlob).mockResolvedValue(new Blob(['docx-bytes']))
    vi.mocked(materialsApi.uploadMaterial).mockResolvedValue({
      material_id: 'mat_ai',
      meeting_id: 'mtg_1',
      file_name: '周会-纪要-v1.docx',
      type: 'docx',
      source: 'AI 生成',
      processing_status: 'processed',
      parse_error: null,
      created_at: '2026-11-05T10:00:00+08:00',
    })
    mirrorMeetingFile.mockResolvedValue('written')
  })

  it('renders the version/template meta and emits open', async () => {
    const wrapper = mount(AgentDocCard, {
      props: { meetingId: 'mtg_1', file: minutesFile, meta: minutesMeta },
    })

    expect(wrapper.text()).toContain('会议纪要 v1')
    // 不再标注状态（草稿/已确认等）
    expect(wrapper.text()).not.toContain('草稿')
    expect(wrapper.text()).toContain('标准纪要')

    await wrapper.get('.doc-card__btn--primary').trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)
  })

  it('saves to the meeting materials and the local folder on click', async () => {
    const wrapper = mount(AgentDocCard, {
      props: { meetingId: 'mtg_1', file: minutesFile, meta: minutesMeta },
    })

    await wrapper.get('[aria-label="保存到会议资料与本地文件夹"]').trigger('click')
    await flushPromises()

    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(1)
    expect(mirrorMeetingFile).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.doc-card__state--saved').exists()).toBe(true)
  })

  it('downloads the DOCX without saving', async () => {
    const wrapper = mount(AgentDocCard, {
      props: { meetingId: 'mtg_1', file: minutesFile, meta: minutesMeta },
    })

    await wrapper.get('[aria-label="下载 DOCX"]').trigger('click')
    await flushPromises()

    expect(downloadBlob).toHaveBeenCalledTimes(1)
    expect(materialsApi.uploadMaterial).not.toHaveBeenCalled()
  })
})

describe('AgentActionItemsCard', () => {
  it('lists items with owner/deadline and emits open', async () => {
    const wrapper = mount(AgentActionItemsCard, { props: { items: actionItems } })

    expect(wrapper.text()).toContain('完成灰度发布检查清单')
    expect(wrapper.text()).toContain('责任人：李雷')
    expect(wrapper.text()).toContain('共 2 条')

    await wrapper.get('.items-card__open').trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)
  })
})

describe('会后产出在聊天中的呈现', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('纪要回复渲染介绍 + 文件卡 + 下一步建议，并可打开右侧抽屉', async () => {
    const { wrapper } = mountChat({
      content: '已生成《项目周会》纪要草稿 v1，状态「draft」。',
      kind: 'minutes',
      file: minutesFile,
      structured: minutesMeta,
    })

    await send(wrapper, '生成纪要')

    expect(wrapper.text()).toContain('已生成《项目周会》纪要草稿 v1')
    expect(wrapper.text()).toContain('会议纪要 v1')

    const suggestions = wrapper.findAll('.agent-suggestion').map((node) => node.text())
    expect(suggestions).toEqual(['打开并编辑', '提取行动项', '再生成一版'])

    await wrapper.findAll('.agent-suggestion')[0].trigger('click')
    expect(wrapper.emitted('open-doc')).toEqual([
      [{ kind: 'minutes', meta: minutesMeta }],
    ])
  })

  it('行动项回复渲染清单卡与建议，正文不再罗列长清单', async () => {
    const { wrapper } = mountChat({
      content: '已提取 2 条行动项候选，并保存为待确认草稿。',
      kind: 'action_items',
      structured: actionItems,
    })

    await send(wrapper, '提取行动项')

    expect(wrapper.text()).toContain('已提取 2 条行动项候选')
    expect(wrapper.find('.items-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('完成灰度发布检查清单')

    const suggestions = wrapper.findAll('.agent-suggestion').map((node) => node.text())
    expect(suggestions).toEqual(['打开确认', '再提取一次'])

    await wrapper.findAll('.agent-suggestion')[0].trigger('click')
    expect(wrapper.emitted('open-doc')).toEqual([
      [{ kind: 'action_items', meta: undefined }],
    ])
  })

  it('普通回复不再显示橙色提示行', async () => {
    const { wrapper } = mountChat({ content: '好的，已结合会议资料回答。', note: '已结合会议资料生成。' })

    await send(wrapper, '总结一下')

    expect(wrapper.text()).toContain('已结合会议资料回答。')
    expect(wrapper.find('.agent-message__status').exists()).toBe(false)
  })
})
