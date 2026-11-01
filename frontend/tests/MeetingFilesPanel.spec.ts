import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as audioApi from '@/api/audio'
import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import * as recordsApi from '@/api/records'
import MeetingFilesPanel from '@/components/MeetingFilesPanel.vue'

vi.mock('@/api/materials', () => ({ listMaterials: vi.fn() }))
vi.mock('@/api/audio', () => ({ listAudio: vi.fn() }))
vi.mock('@/api/minutes', () => ({ listMinutes: vi.fn() }))
vi.mock('@/api/records', () => ({ listRecords: vi.fn() }))

function listOf<T>(items: T[]) {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

describe('MeetingFilesPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([]))
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([]))
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([]))
    vi.mocked(recordsApi.listRecords).mockResolvedValue(
      listOf([
        {
          record_id: 'rec_1',
          meeting_id: 'mtg_1',
          content: '张三：本周完成登录模块联调。',
          record_type: 'manual',
          marker_type: null,
          source_material_id: null,
          created_at: '2026-10-29T09:24:00+08:00',
          updated_at: '2026-10-29T09:24:00+08:00',
        },
      ]),
    )
  })

  it('renders the four file groups with counts and empty hints', async () => {
    const wrapper = mount(MeetingFilesPanel, { props: { meetingId: 'mtg_1' } })
    await flushPromises()

    const titles = wrapper.findAll('.file-group__title').map((node) => node.text())
    expect(titles).toEqual(['会议资料', '录音', '纪要', '会议记录'])
    expect(wrapper.text()).toContain('未上传资料')
    expect(wrapper.text()).toContain('未上传录音')
    expect(wrapper.text()).toContain('尚未生成纪要')
    expect(wrapper.text()).toContain('1 条')
  })

  it('previews a meeting record inline', async () => {
    const wrapper = mount(MeetingFilesPanel, { props: { meetingId: 'mtg_1' } })
    await flushPromises()

    const previewButton = wrapper.findAll('button').find((node) => node.text() === '预览')
    await previewButton?.trigger('click')

    expect(wrapper.text()).toContain('手动记录')
    expect(wrapper.text()).toContain('张三：本周完成登录模块联调。')
  })

  it('shows pending badges for materials and audio', async () => {
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(
      listOf([
        {
          material_id: 'mat_1',
          meeting_id: 'mtg_1',
          file_name: '产品白皮书.pdf',
          type: 'pdf',
          source: null,
          processing_status: 'processed',
          parse_error: null,
          created_at: '2026-10-01T09:00:00+08:00',
        },
      ]),
    )
    const wrapper = mount(MeetingFilesPanel, { props: { meetingId: 'mtg_1' } })
    await flushPromises()

    expect(wrapper.text()).toContain('产品白皮书.pdf')
    expect(wrapper.text()).toContain('待开放')
  })

  it('reloads when the meetingId prop changes', async () => {
    const wrapper = mount(MeetingFilesPanel, { props: { meetingId: 'mtg_1' } })
    await flushPromises()
    expect(recordsApi.listRecords).toHaveBeenCalledWith('mtg_1', { page: 1, page_size: 50 })

    await wrapper.setProps({ meetingId: 'mtg_2' })
    await flushPromises()
    expect(recordsApi.listRecords).toHaveBeenCalledWith('mtg_2', { page: 1, page_size: 50 })
  })
})
