import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import LocalWorkspacePanel from '@/components/LocalWorkspacePanel.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import type { ListData } from '@/types/api'
import type { Material } from '@/types/material'
import * as minutesDocx from '@/utils/minutesDocx'

vi.mock('@/api/materials', () => ({
  uploadMaterial: vi.fn(),
  listMaterials: vi.fn(),
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

interface DirectoryMockOptions {
  /** queryPermission 返回值，默认 granted */
  permission?: PermissionState
  /** requestPermission 返回值（恢复权限用），默认跟随 permission */
  requestResult?: PermissionState
}

function createDirectory(entries: FileEntry[], options: DirectoryMockOptions = {}) {
  const write = vi.fn().mockResolvedValue(undefined)
  const close = vi.fn().mockResolvedValue(undefined)
  const getFileHandle = vi.fn().mockResolvedValue({
    createWritable: vi.fn().mockResolvedValue({ write, close }),
  })
  const directory: Record<string, unknown> = {
    kind: 'directory' as const,
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
    getDirectoryHandle: vi.fn(async () => directory),
    queryPermission: vi.fn(async () => options.permission ?? 'granted'),
    requestPermission: vi.fn(async () => options.requestResult ?? options.permission ?? 'granted'),
    _write: write,
    _close: close,
  }
  return directory
}

function mountPanel(readonly = false): VueWrapper {
  return mount(LocalWorkspacePanel, {
    props: { meetingId: 'mtg_1', meetingTitle: '项目周会', readonly },
  })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text().includes(text))
}

function materialOf(fileName: string): Material {
  return {
    material_id: `mat_${fileName}`,
    meeting_id: 'mtg_1',
    file_name: fileName,
    type: 'txt',
    source: '本地工作区',
    processing_status: 'processed',
    parse_error: null,
    created_at: '2026-10-01T09:00:00+08:00',
  }
}

function materialList(items: Material[]): ListData<Material> {
  return {
    items,
    pagination: { page: 1, page_size: 100, total: items.length, total_pages: 1 },
  }
}

describe('LocalWorkspacePanel', () => {
  beforeEach(async () => {
    // 面板已统一到共享目录句柄：每个用例前重置单例，避免句柄/状态串味
    await useLocalWorkspace().disconnect()
    vi.resetAllMocks()
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(materialList([]))
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

  it('shows a reminder for local files not yet imported', async () => {
    const directory = createDirectory([
      { name: 'old.txt', file: new File(['old'], 'old.txt') },
      { name: 'plan.txt', file: new File(['plan'], 'plan.txt') },
    ])
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: vi.fn().mockResolvedValue(directory),
      configurable: true,
    })
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(materialList([materialOf('old.txt')]))
    const wrapper = mountPanel()

    await button(wrapper, '选择本地文件夹')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('检测到 1 个本地新文件尚未导入该会议')
  })

  it('imports only the new files from the reminder', async () => {
    const newFile = new File(['plan'], 'plan.txt')
    const directory = createDirectory([
      { name: 'old.txt', file: new File(['old'], 'old.txt') },
      { name: 'plan.txt', file: newFile },
    ])
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: vi.fn().mockResolvedValue(directory),
      configurable: true,
    })
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(materialList([materialOf('old.txt')]))
    vi.mocked(materialsApi.uploadMaterial).mockResolvedValue(materialOf('plan.txt'))
    const wrapper = mountPanel()

    await button(wrapper, '选择本地文件夹')?.trigger('click')
    await flushPromises()
    await button(wrapper, '仅导入新文件')?.trigger('click')
    await flushPromises()

    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(1)
    expect(materialsApi.uploadMaterial).toHaveBeenCalledWith('mtg_1', {
      file: newFile,
      source: '本地工作区',
    })
    expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(wrapper.text()).toContain('已导入 1 个新文件')
    expect(wrapper.text()).not.toContain('检测到')
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

    // 默认会议根 = <会议名>/，纪要写入其中
    expect(directory.getDirectoryHandle).toHaveBeenCalledWith('项目周会', { create: true })
    expect(directory.getFileHandle).toHaveBeenCalledWith('项目周会-会议纪要.docx', {
      create: true,
    })
    expect(directory._write).toHaveBeenCalledWith(blob)
    expect(directory._close).toHaveBeenCalled()
    expect(wrapper.text()).toContain('最新纪要已导出到本地文件夹')
  })

  it('shows a restore banner when permission expires and recovers in place', async () => {
    const directory = createDirectory(
      [{ name: 'plan.txt', file: new File(['plan'], 'plan.txt') }],
      { permission: 'prompt', requestResult: 'prompt' },
    )
    Object.defineProperty(window, 'showDirectoryPicker', {
      value: vi.fn().mockResolvedValue(directory),
      configurable: true,
    })
    const wrapper = mountPanel()

    // 选择目录后权限未授予 → 进入 needs-permission，展示恢复入口
    await button(wrapper, '选择本地文件夹')?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('本地文件夹权限已过期或被撤销')
    const restoreBtn = button(wrapper, '恢复权限')
    expect(restoreBtn).toBeTruthy()

    // 一键恢复（手势内弹窗）→ granted → 文件列表可用，无需重新选目录
    directory.requestPermission = vi.fn(async () => 'granted' as PermissionState)
    await restoreBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('本地文件夹权限已恢复')
    expect(wrapper.text()).toContain('plan.txt')
    expect(wrapper.text()).not.toContain('权限已过期或被撤销')
  })
})
