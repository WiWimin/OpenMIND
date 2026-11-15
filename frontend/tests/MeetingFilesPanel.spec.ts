import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as audioApi from '@/api/audio'
import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import * as recordsApi from '@/api/records'
import MeetingFilesPanel from '@/components/MeetingFilesPanel.vue'
import { recordFileName } from '@/utils/meetingFiles'

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

  it('renders one flat explorer list without source group headings', async () => {
    const wrapper = mount(MeetingFilesPanel, { props: { meetingId: 'mtg_1' } })
    await flushPromises()

    // 仿资源管理器：名称 / 修改日期 / 类型 三列表头
    const headers = wrapper.findAll('.file-explorer__head .file-explorer__col').map((node) =>
      node.text().trim(),
    )
    expect(headers).toEqual(['名称', '修改日期', '类型', '操作'])

    // 不再按来源分组
    expect(wrapper.findAll('.file-group').length).toBe(0)
    expect(wrapper.find('.file-explorer').exists()).toBe(true)

    // 保存后的会议记录以 .md 文件条目混排进同一列表。
    // 文件名由生产侧命名函数生成（本地时区），断言不能写死时刻，否则 CI（UTC）会差 8 小时
    expect(wrapper.text()).toContain(
      recordFileName({ record_id: 'rec_1', created_at: '2026-10-29T09:24:00+08:00' }),
    )
    expect(wrapper.text()).toMatch(/会议记录_\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.md/)
  })

  it('previews a saved record inline', async () => {
    const wrapper = mount(MeetingFilesPanel, { props: { meetingId: 'mtg_1' } })
    await flushPromises()

    const row = wrapper
      .findAll('.file-explorer__row')
      .find((node) => node.text().includes('会议记录_'))
    await row?.trigger('click')

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
    // 类型列由扩展名生成（PDF 文档），不显示文件大小
    expect(wrapper.text()).toContain('PDF 文档')
    expect(wrapper.text()).toContain('待开放')
    expect(wrapper.text()).not.toContain('大小')
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
