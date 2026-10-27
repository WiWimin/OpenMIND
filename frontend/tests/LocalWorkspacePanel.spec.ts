import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import LocalWorkspacePanel from '@/components/LocalWorkspacePanel.vue'
import * as minutesDocx from '@/utils/minutesDocx'

vi.mock('@/api/materials', () => ({
  uploadMaterial: vi.fn(),
}))

vi.mock('@/api/minutes', () => ({
  listMinutes: vi.fn(),
}))

vi.mock('@/utils/minutesDocx', () => ({
  buildMinutesDocxBlob: vi.fn(),
}))

const minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '<p>会议纪要</p>',
  status: 'draft' as const,
  version: 1,
  template: 'standard' as const,
  source_record_ids: [],
  source_material_ids: [],
  created_at: '2026-10-01T10:00:00+08:00',
  updated_at: '2026-10-01T10:00:00+08:00',
}

type FileEntry = { name: string; file: File }

function createDirectory(entries: FileEntry[]) {
  const write = vi.fn().mockResolvedValue(undefined)
  const close = vi.fn().mockResolvedValue(undefined)
  const getFileHandle = vi.fn().mockResolvedValue({
    createWritable: vi.fn().mockResolvedValue({ write, close }),
  })
  return {
    name: 'meeting-files',
    values: async function* () {
      for (const entry of entries) {
        yield {
          kind: 'file' as const,
          name: entry.name,
          getFile: async () => entry.file,
        }
      }
    },
    getFileHandle,
    _write: write,
    _close: close,
  }
}

function mountPanel(readonly = false): VueWrapper {
  return mount(LocalWorkspacePanel, {
    props: { meetingId: 'mtg_1', meetingTitle: '项目周会', readonly },
  })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text().includes(text))
}

describe('LocalWorkspacePanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: undefined,
      configurable: true,
    })
  })

  it('shows an unsupported browser hint', () => {
    const wrapper = mountPanel()
    expect(wrapper.text()).toContain('当前浏览器不支持本地文件夹访问')
  })

  it('lists supported files from the selected directory', async () => {
    const directory = createDirectory([
      { name: 'plan.txt', file: new File(['plan'], 'plan.txt') },
      { name: 'skip.exe', file: new File(['x'], 'skip.exe') },
    ])
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: vi.fn().mockResolvedValue(directory),
      configurable: true,
    })
    const wrapper = mountPanel()

    await button(wrapper, '选择本地文件夹')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('meeting-files')
    expect(wrapper.text()).toContain('plan.txt')
    expect(wrapper.text()).not.toContain('skip.exe')
  })

  it('imports local files into the meeting', async () => {
    const file = new File(['plan'], 'plan.txt')
    const directory = createDirectory([{ name: 'plan.txt', file }])
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: vi.fn().mockResolvedValue(directory),
      configurable: true,
    })
    vi.mocked(materialsApi.uploadMaterial).mockResolvedValue({
      material_id: 'mat_1',
      meeting_id: 'mtg_1',
      file_name: 'plan.txt',
      type: 'txt',
      source: '本地工作区',
      processing_status: 'processed',
      parse_error: null,
      created_at: '2026-10-01T09:00:00+08:00',
    })
    const wrapper = mountPanel()

    await button(wrapper, '选择本地文件夹')?.trigger('click')
    await flushPromises()
    await button(wrapper, '导入资料')?.trigger('click')
    await flushPromises()

    expect(materialsApi.uploadMaterial).toHaveBeenCalledWith('mtg_1', {
      file,
      source: '本地工作区',
    })
    expect(wrapper.emitted('imported')).toHaveLength(1)
  })

  it('exports the latest minutes to the selected directory', async () => {
    const directory = createDirectory([])
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: vi.fn().mockResolvedValue(directory),
      configurable: true,
    })
    vi.mocked(minutesApi.listMinutes).mockResolvedValue({
      items: [minutes],
      pagination: { page: 1, page_size: 1, total: 1, total_pages: 1 },
    })
    const blob = new Blob(['docx'])
    vi.mocked(minutesDocx.buildMinutesDocxBlob).mockResolvedValue(blob)
    const wrapper = mountPanel()

    await button(wrapper, '选择本地文件夹')?.trigger('click')
    await flushPromises()
    await button(wrapper, '导出最新纪要')?.trigger('click')
    await flushPromises()

    expect(directory.getFileHandle).toHaveBeenCalledWith('项目周会-会议纪要.docx', {
      create: true,
    })
    expect(directory._write).toHaveBeenCalledWith(blob)
    expect(directory._close).toHaveBeenCalled()
    expect(wrapper.text()).toContain('最新纪要已导出到本地文件夹')
  })
})
