/**
 * 会议工作区的 `.openmind/manifest.json`：可移植的同步基线镜像。
 *
 * 作用：IndexedDB 被清空、换浏览器或换设备时，能从目录里的清单恢复基线，
 * 避免「全量重新导入」或「重复上传」。IDB 仍是唯一事实来源，清单只做镜像。
 */

import {
  readTextAtRelPath,
  writeTextAtRelPath,
  toLocalFsError,
  type LocalDirHandle,
} from '@/utils/localFileSystem'
import type { SyncBaseline, SyncConflict } from '@/types/localWorkspace'

export const MANIFEST_DIR = '.openmind'
export const MANIFEST_FILE = 'manifest.json'

export interface WorkspaceManifest {
  schema: number
  app: string
  meetingId: string
  meetingTitle: string
  layout: number
  generatedAt: string
  entries: Record<string, SyncBaseline>
  conflicts: SyncConflict[]
}

export function emptyManifest(meetingId: string, meetingTitle: string): WorkspaceManifest {
  return {
    schema: 2,
    app: 'OpenMIND',
    meetingId,
    meetingTitle,
    layout: 1,
    generatedAt: new Date().toISOString(),
    entries: {},
    conflicts: [],
  }
}

export function buildManifest(
  meetingId: string,
  meetingTitle: string,
  baselines: SyncBaseline[],
  conflicts: SyncConflict[],
): WorkspaceManifest {
  const entries: Record<string, SyncBaseline> = {}
  for (const item of baselines) {
    entries[item.relPath] = item
  }
  return {
    ...emptyManifest(meetingId, meetingTitle),
    generatedAt: new Date().toISOString(),
    entries,
    conflicts,
  }
}

/** 读取清单；不存在或损坏时返回 null（调用方按「空清单」处理并从 IDB 重建） */
export async function readManifest(
  root: LocalDirHandle,
  meetingRoot: string[],
): Promise<WorkspaceManifest | null> {
  try {
    const raw = await readTextAtRelPath(root, meetingRoot, `${MANIFEST_DIR}/${MANIFEST_FILE}`)
    return parseManifest(raw)
  } catch {
    return null
  }
}

export function parseManifest(raw: string): WorkspaceManifest | null {
  try {
    const parsed = JSON.parse(raw) as Partial<WorkspaceManifest>
    if (typeof parsed !== 'object' || parsed === null) {
      return null
    }
    if (parsed.schema !== 2 || typeof parsed.meetingId !== 'string') {
      return null
    }
    return {
      schema: 2,
      app: parsed.app ?? 'OpenMIND',
      meetingId: parsed.meetingId,
      meetingTitle: parsed.meetingTitle ?? '',
      layout: parsed.layout ?? 1,
      generatedAt: parsed.generatedAt ?? new Date().toISOString(),
      entries: parsed.entries ?? {},
      conflicts: parsed.conflicts ?? [],
    }
  } catch {
    return null
  }
}

/**
 * 写入清单。失败只上报，不阻断同步（清单是镜像，不是事实来源）。
 * 使用一次性序列化 + 覆盖写；文件很小，不引入临时文件移动的复杂度。
 */
export async function writeManifest(
  root: LocalDirHandle,
  meetingRoot: string[],
  manifest: WorkspaceManifest,
): Promise<void> {
  try {
    await writeTextAtRelPath(
      root,
      meetingRoot,
      `${MANIFEST_DIR}/${MANIFEST_FILE}`,
      JSON.stringify(manifest, null, 2),
    )
  } catch (caught) {
    throw toLocalFsError(caught, '同步清单写入失败')
  }
}
