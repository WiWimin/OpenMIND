import { computed, ref, shallowRef } from 'vue'

import * as meetingsApi from '@/api/meetings'
import {
  clearStoredHandle,
  ensureLocalDir,
  isLocalWorkspaceSupported,
  isWriteAllowed,
  listSubdirs,
  loadMeetingRoot,
  loadStoredHandle,
  pickDirectory,
  queryPermission,
  requestPermission,
  sanitizeFolderName,
  storeHandle,
  writeBlobToPath,
  type LocalDirHandle,
} from '@/utils/localFileSystem'

export type WorkspaceStatus = 'unsupported' | 'unconfigured' | 'needs-permission' | 'connected'

/** 全局单例：整个应用共享同一个已授权目录 */
const handle = shallowRef<LocalDirHandle | null>(null)
const permission = ref<PermissionState>('denied')

const status = computed<WorkspaceStatus>(() => {
  if (!isLocalWorkspaceSupported()) {
    return 'unsupported'
  }
  if (!handle.value) {
    return 'unconfigured'
  }
  return isWriteAllowed(permission.value) ? 'connected' : 'needs-permission'
})

const directoryName = computed(() => handle.value?.name ?? '')

/** 会议标题缓存，避免每次镜像都请求会议详情 */
const titleCache = new Map<string, string>()

async function resolveMeetingTitle(meetingId: string): Promise<string> {
  const cached = titleCache.get(meetingId)
  if (cached) {
    return cached
  }
  try {
    const meeting = await meetingsApi.getMeeting(meetingId)
    titleCache.set(meetingId, meeting.title)
    return meeting.title
  } catch {
    return meetingId
  }
}

async function init(): Promise<void> {
  if (!isLocalWorkspaceSupported() || handle.value) {
    return
  }
  const stored = await loadStoredHandle()
  if (!stored) {
    return
  }
  handle.value = stored
  permission.value = await queryPermission(stored)
}

/** 打开原生目录选择窗口；成功后持久化句柄 */
async function connect(): Promise<boolean> {
  if (!isLocalWorkspaceSupported()) {
    return false
  }
  const picked = await pickDirectory()
  if (!picked) {
    return false
  }
  handle.value = picked
  permission.value = await queryPermission(picked)
  try {
    await storeHandle(picked)
  } catch {
    /* 持久化失败不影响本次会话使用 */
  }
  if (permission.value !== 'granted') {
    permission.value = await requestPermission(picked)
  }
  return isWriteAllowed(permission.value)
}

/** 权限过期后的一键恢复（浏览器原生弹窗，无需重新选目录） */
async function restore(): Promise<boolean> {
  const current = handle.value
  if (!current) {
    return false
  }
  permission.value = await requestPermission(current)
  return isWriteAllowed(permission.value)
}

async function disconnect(): Promise<void> {
  handle.value = null
  permission.value = 'denied'
  try {
    await clearStoredHandle()
  } catch {
    /* 忽略清理失败 */
  }
}

export interface MirrorMeetingFileOptions {
  meetingId: string
  /** meetingTitle 缺省时自动调用会议详情接口解析 */
  meetingTitle?: string
  fileName: string
  content: Blob | string
}

/** skipped：未连接本地文件夹（正常降级）；written：写入成功；failed：已连接但写入失败 */
export type MirrorResult = 'skipped' | 'written' | 'failed'

/**
 * 解析会议的本地存储根（路径即会议根）：
 * 1) 新建会议时显式选择的路径（IndexedDB 持久化）；
 * 2) 未选择时默认「授权目录/<会议名>/」。
 */
async function meetingRootSegments(meetingId: string, title: string): Promise<string[]> {
  try {
    const stored = await loadMeetingRoot(meetingId)
    if (stored && stored.length > 0) {
      return stored
    }
  } catch {
    /* 读取失败走默认 */
  }
  return [sanitizeFolderName(title)]
}

/** 创建会议时的默认落盘：若已连接，在授权目录创建 <会议名>/ 文件夹 */
async function createDefaultMeetingFolder(title: string): Promise<void> {
  if (status.value !== 'connected' || !handle.value) {
    return
  }
  try {
    await ensureLocalDir(handle.value, [sanitizeFolderName(title)])
  } catch (caught) {
    console.warn('[local-workspace] 默认会议文件夹创建失败', caught)
  }
}

/**
 * 把会议相关文件镜像写入本地「授权目录/<会议根>/<文件>」。
 * 未授权时返回 skipped 静默降级，绝不影响主流程。
 */
async function mirrorMeetingFile(options: MirrorMeetingFileOptions): Promise<MirrorResult> {
  if (status.value !== 'connected' || !handle.value) {
    return 'skipped'
  }
  try {
    const title = options.meetingTitle ?? (await resolveMeetingTitle(options.meetingId))
    const segments = await meetingRootSegments(options.meetingId, title)
    const content =
      typeof options.content === 'string'
        ? new Blob([options.content], { type: 'text/plain;charset=utf-8' })
        : options.content
    await writeBlobToPath(handle.value, segments, sanitizeFolderName(options.fileName), content)
    return 'written'
  } catch (caught) {
    console.warn('[local-workspace] 本地镜像写入失败', caught)
    return 'failed'
  }
}

/**
 * 把用户确认后的纪要写入本地「授权目录/OpenMIND/<分类>/<会议>/纪要/会议纪要_<会议标题>.md」。
 * 确认版文件名固定：同一版本重复确认覆盖写入，不产生草稿版本残留。
 * 未连接本地文件夹时直接跳过，不发起会议标题解析请求。
 */
async function mirrorConfirmedMinutes(
  meetingId: string,
  content: string,
  meetingTitle?: string,
): Promise<MirrorResult> {
  if (status.value !== 'connected' || !handle.value) {
    return 'skipped'
  }
  const title = meetingTitle || (await resolveMeetingTitle(meetingId))
  return mirrorMeetingFile({
    meetingId,
    meetingTitle: title,
    fileName: `会议纪要_${title}.md`,
    content,
  })
}

export function useLocalWorkspace() {
  return {
    status,
    directoryName,
    rootHandle: handle,
    init,
    connect,
    restore,
    disconnect,
    mirrorMeetingFile,
    mirrorConfirmedMinutes,
    meetingRootSegments,
    createDefaultMeetingFolder,
    listSubdirs,
  }
}
