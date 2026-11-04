import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as materialsApi from '@/api/materials'
import ChatFileCard from '@/components/ChatFileCard.vue'
import type { ChatFile } from '@/types/chat'
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

const file: ChatFile = {
  filename: 'q3-budget.md',
  content: '# Q3 预算\n\n- 市场投放 120 万',
}

function mountCard() {
  return mount(ChatFileCard, { props: { meetingId: 'mtg_1', file } })
}

describe('ChatFileCard', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(minutesDocx.buildMinutesDocxBlob).mockResolvedValue(new Blob(['docx-bytes']))
    vi.mocked(materialsApi.uploadMaterial).mockResolvedValue({
      material_id: 'mat_ai',
      meeting_id: 'mtg_1',
      file_name: 'q3-budget.docx',
      type: 'docx',
      source: 'AI 生成',
      processing_status: 'processed',
      parse_error: null,
      created_at: '2026-11-04T10:00:00+08:00',
    })
    mirrorMeetingFile.mockResolvedValue('written')
  })

  it('saves to meeting materials and mirrors to the local folder in parallel', async () => {
    const wrapper = mountCard()
    await flushPromises()

    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(1)
    const [meetingId, payload] = vi.mocked(materialsApi.uploadMaterial).mock.calls[0]
    expect(meetingId).toBe('mtg_1')
    expect(payload.source).toBe('AI 生成')
    expect(payload.file.name).toBe('q3-budget.docx')
    expect(mirrorMeetingFile).toHaveBeenCalledTimes(1)
    expect(mirrorMeetingFile).toHaveBeenCalledWith(
      expect.objectContaining({
        meetingId: 'mtg_1',
        fileName: 'q3-budget.docx',
      }),
    )

    expect(wrapper.text()).toContain('已保存到会议资料')
    expect(wrapper.text()).toContain('已写入本地文件夹')
  })

  it('shows a per-item retry when the meeting save fails', async () => {
    vi.mocked(materialsApi.uploadMaterial)
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({
        material_id: 'mat_ai',
        meeting_id: 'mtg_1',
        file_name: 'q3-budget.docx',
        type: 'docx',
        source: 'AI 生成',
        processing_status: 'processed',
        parse_error: null,
        created_at: '2026-11-04T10:00:00+08:00',
      })
    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.text()).toContain('保存到会议资料失败')

    const retry = wrapper.findAll('button').find((b) => b.text() === '重试')
    await retry?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已保存到会议资料')
    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(2)
  })

  it('marks the local mirror as skipped when the folder is not connected', async () => {
    mirrorMeetingFile.mockResolvedValue('skipped')
    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.text()).toContain('未连接本地文件夹')
    expect(wrapper.text()).not.toContain('本地写入失败')
  })

  it('downloads the docx with a .docx filename', async () => {
    const wrapper = mountCard()
    await flushPromises()

    const download = wrapper.findAll('button').find((b) => b.text() === '下载 DOCX')
    await download?.trigger('click')
    await flushPromises()

    expect(downloadBlob).toHaveBeenCalledTimes(1)
    expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'q3-budget.docx')
  })
})
