/**
 * 新建会议后从所选本地文件夹自动导入已有资料。
 *
 * 语义 = 手动「导入资料」的无人值守等价物，边界完全一致：
 * - 白名单：`ALLOWED_MATERIAL_EXTENSIONS`（pdf/docx/txt），与手动入口同一常量；
 * - 递归：只读所选会议根第一层，不进入子目录；
 * - 上限：单次 50 个文件（超出报 truncated），单文件 20MB（`MAX_UPLOAD_MB`，前端预筛，后端兜底）；
 * - 去重键：文件名精确匹配（后端无唯一约束，同名视为已导入，不做内容比对/覆盖）；
 * - 失败：单文件失败只记录不阻塞其余文件，绝不抛出（权限/读目录级失败由上层捕获提示）。
 */
import * as materialsApi from '@/api/materials'
import { ALLOWED_MATERIAL_EXTENSIONS, MAX_UPLOAD_MB } from '@/constants/upload'
import { readFilesAt, type LocalDirHandle, type LocalFileEntry } from '@/utils/localFileSystem'
import { resolveErrorMessage } from '@/utils/errors'
import { isAllowedExtension } from '@/utils/materialUpload'

/** 单次自动导入的文件数上限（与手动面板一致） */
export const AUTO_IMPORT_MAX_FILES = 50

/** 自动导入写入的资料来源标识（materials.source） */
export const AUTO_IMPORT_SOURCE = '本地文件夹自动导入'

export interface AutoImportProgress {
  /** 已处理（含跳过）数量 */
  done: number
  /** 候选总数（白名单 + 未超限） */
  total: number
  /** 正在处理的文件名 */
  fileName: string
}

export interface AutoImportResult {
  imported: string[]
  /** 同名已存在而跳过 */
  skipped: string[]
  /** 扩展名不在白名单 */
  unsupported: string[]
  /** 超过 MAX_UPLOAD_MB */
  oversized: string[]
  failed: { name: string; reason: string }[]
  /** 候选文件超出 AUTO_IMPORT_MAX_FILES 上限，尾部未读取 */
  truncated: boolean
}

export interface AutoImportOptions {
  meetingId: string
  root: LocalDirHandle
  /** 会议根路径段（新建会议时选择的存储位置） */
  segments: string[]
  onProgress?: (progress: AutoImportProgress) => void
}

/** 分页回取已有资料文件名（最多 10 页 / 1000 条，防御异常分页死循环） */
async function loadExistingNames(meetingId: string): Promise<Set<string>> {
  const names = new Set<string>()
  const pageSize = 100
  for (let page = 1; page <= 10; page += 1) {
    const result = await materialsApi.listMaterials(meetingId, { page, page_size: pageSize })
    for (const item of result.items) {
      names.add(item.file_name)
    }
    if (page * pageSize >= result.pagination.total) {
      break
    }
  }
  return names
}

/**
 * 自动导入会议根下的已有资料。
 *
 * 不会因单个文件失败而抛出；但「读取已有资料列表」失败会抛出
 * （无法去重时继续导入会产生重复记录，应由上层提示并放弃本次自动导入）。
 */
export async function autoImportMeetingFiles(
  options: AutoImportOptions,
): Promise<AutoImportResult> {
  const { meetingId, root, segments, onProgress } = options
  const result: AutoImportResult = {
    imported: [],
    skipped: [],
    unsupported: [],
    oversized: [],
    failed: [],
    truncated: false,
  }

  const { files, truncated } = await readFilesAt(root, segments, AUTO_IMPORT_MAX_FILES)
  result.truncated = truncated

  const candidates: LocalFileEntry[] = []
  for (const entry of files) {
    if (!isAllowedExtension(entry.name, ALLOWED_MATERIAL_EXTENSIONS)) {
      result.unsupported.push(entry.name)
      continue
    }
    if (entry.size > MAX_UPLOAD_MB * 1024 * 1024) {
      result.oversized.push(entry.name)
      continue
    }
    candidates.push(entry)
  }
  if (candidates.length === 0) {
    return result
  }

  // 先取已有资料文件名再逐个上传：同名跳过（幂等，防重复创建会议/重跑产生重复）
  const existing = await loadExistingNames(meetingId)

  let done = 0
  for (const entry of candidates) {
    done += 1
    onProgress?.({ done, total: candidates.length, fileName: entry.name })
    if (existing.has(entry.name)) {
      result.skipped.push(entry.name)
      continue
    }
    try {
      await materialsApi.uploadMaterial(meetingId, {
        file: entry.file,
        source: AUTO_IMPORT_SOURCE,
      })
      result.imported.push(entry.name)
      existing.add(entry.name)
    } catch (caught) {
      result.failed.push({ name: entry.name, reason: resolveErrorMessage(caught, '上传失败') })
    }
  }
  return result
}
