import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as materialsApi from '@/api/materials'
import {
  AUTO_IMPORT_MAX_FILES,
  AUTO_IMPORT_SOURCE,
  autoImportMeetingFiles,
  type AutoImportProgress,
} from '@/utils/autoImport'
import type { LocalDirHandle, LocalFileEntry } from '@/utils/localFileSystem'

const readFilesAt = vi.fn<
  (root: LocalDirHandle, segments: string[], limit?: number) => Promise<{
    files: LocalFileEntry[]
    truncated: boolean
  }>
>()

vi.mock('@/utils/localFileSystem', () => ({
  readFilesAt: (root: LocalDirHandle, segments: string[], limit?: number) =>
    readFilesAt(root, segments, limit),
}))

vi.mock('@/api/materials', () => ({
  listMaterials: vi.fn(),
  uploadMaterial: vi.fn(),
}))

const root = { name: 'demo' } as LocalDirHandle

function entry(name: string, content = 'x', size?: number): LocalFileEntry {
  const file = new File([content], name)
  return { name, file, size: size ?? file.size }
}

function materialList(names: string[], total = names.length) {
  return {
    items: names.map((name) => ({ file_name: name })),
    pagination: { page: 1, page_size: 100, total, total_pages: 1 },
  }
}

function importFiles(
  overrides: Partial<Parameters<typeof autoImportMeetingFiles>[0]> = {},
) {
  return autoImportMeetingFiles({
    meetingId: 'mtg_1',
    root,
    segments: ['项目周会'],
    ...overrides,
  })
}

describe('autoImportMeetingFiles', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(materialList([]) as never)
    vi.mocked(materialsApi.uploadMaterial).mockResolvedValue({} as never)
    readFilesAt.mockResolvedValue({ files: [], truncated: false })
  })

  it('reads the meeting root path with the shared limit', async () => {
    await importFiles()

    expect(readFilesAt).toHaveBeenCalledWith(root, ['项目周会'], AUTO_IMPORT_MAX_FILES)
    // 没有候选文件时不拉取已有资料列表（省一次请求）
    expect(materialsApi.listMaterials).not.toHaveBeenCalled()
  })

  it('filters by whitelist and size, then uploads with the auto-import source', async () => {
    readFilesAt.mockResolvedValue({
      files: [
        entry('a.pdf'),
        entry('b.docx'),
        entry('c.txt'),
        entry('photo.png'), // 白名单外
        entry('huge.pdf', 'x', 21 * 1024 * 1024), // 超过 20MB
      ],
      truncated: false,
    })

    const result = await importFiles()

    expect(result.imported).toEqual(['a.pdf', 'b.docx', 'c.txt'])
    expect(result.unsupported).toEqual(['photo.png'])
    expect(result.oversized).toEqual(['huge.pdf'])
    expect(result.failed).toEqual([])
    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(3)
    for (const [, payload] of vi.mocked(materialsApi.uploadMaterial).mock.calls) {
      expect(payload.source).toBe(AUTO_IMPORT_SOURCE)
    }
  })

  it('skips files whose name already exists in the meeting (idempotent)', async () => {
    readFilesAt.mockResolvedValue({
      files: [entry('a.pdf'), entry('b.pdf')],
      truncated: false,
    })
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(
      materialList(['a.pdf']) as never,
    )

    const result = await importFiles()

    expect(result.imported).toEqual(['b.pdf'])
    expect(result.skipped).toEqual(['a.pdf'])
    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(1)
    expect(vi.mocked(materialsApi.uploadMaterial).mock.calls[0][1].file.name).toBe('b.pdf')
  })

  it('keeps importing after a single file failure and reports the reason', async () => {
    readFilesAt.mockResolvedValue({
      files: [entry('a.pdf'), entry('b.pdf')],
      truncated: false,
    })
    vi.mocked(materialsApi.uploadMaterial)
      .mockRejectedValueOnce(new Error('网络中断'))
      .mockResolvedValueOnce({} as never)

    const result = await importFiles()

    expect(result.imported).toEqual(['b.pdf'])
    expect(result.failed).toHaveLength(1)
    expect(result.failed[0].name).toBe('a.pdf')
    expect(result.failed[0].reason).toContain('网络中断')
    expect(materialsApi.uploadMaterial).toHaveBeenCalledTimes(2)
  })

  it('emits serial progress for each candidate', async () => {
    readFilesAt.mockResolvedValue({
      files: [entry('a.pdf'), entry('b.pdf')],
      truncated: false,
    })
    const progress: AutoImportProgress[] = []

    await importFiles({ onProgress: (item) => progress.push(item) })

    expect(progress).toEqual([
      { done: 1, total: 2, fileName: 'a.pdf' },
      { done: 2, total: 2, fileName: 'b.pdf' },
    ])
  })

  it('propagates the existing-list failure (dedupe unavailable)', async () => {
    readFilesAt.mockResolvedValue({
      files: [entry('a.pdf')],
      truncated: false,
    })
    vi.mocked(materialsApi.listMaterials).mockRejectedValue(new Error('500'))

    await expect(importFiles()).rejects.toThrow('500')
    expect(materialsApi.uploadMaterial).not.toHaveBeenCalled()
  })

  it('carries the truncation flag from the directory read', async () => {
    readFilesAt.mockResolvedValue({
      files: [entry('a.pdf')],
      truncated: true,
    })

    const result = await importFiles()

    expect(result.truncated).toBe(true)
    expect(result.imported).toEqual(['a.pdf'])
  })

  it('does nothing when every file is filtered out', async () => {
    readFilesAt.mockResolvedValue({
      files: [entry('photo.png')],
      truncated: false,
    })

    const result = await importFiles()

    expect(result).toEqual({
      imported: [],
      skipped: [],
      unsupported: ['photo.png'],
      oversized: [],
      failed: [],
      truncated: false,
    })
    expect(materialsApi.listMaterials).not.toHaveBeenCalled()
    expect(materialsApi.uploadMaterial).not.toHaveBeenCalled()
  })
})
