import { computed, ref, shallowRef } from 'vue'

import * as meetingsApi from '@/api/meetings'
import { useAuthStore } from '@/stores/auth'
import { executeConfirmedPush, runSync, type RunSyncContext } from '@/services/localSync/runSync'
import { workspaceWatcher } from '@/composables/useWorkspaceWatcher'
import {
  clearMeetingRoot,
  clearRootHandle,
  clearStoredHandle,
  ensureLocalDir,
  isLocalWorkspaceSupported,
  isWriteAllowed,
  listSubdirs,
  loadBaselines,
  loadConflicts,
  loadMeetingRoot,
  loadPrefs,
  loadRootHandle,
  loadStoredHandle,
  moveDirPath,
  pickDirectory,
  queryPermission,
  removeDirPath,
  requestPermission,
  resolveConflict as resolveStoredConflict,
  sanitizeFolderName,
  saveBaselineFor,
  savePrefs,
  storeHandle,
  storeMeetingRoot,
  storeRootHandle,
  writeBlobToPath,
  type LocalDirHandle,
  type StoredConflict,
} from '@/utils/localFileSystem'
import type { SyncSummary } from '@/types/localWorkspace'
import { categoryOf, categoryNameOf } from '@/utils/meetingCategories'

export type WorkspaceStatus = 'unsupported' | 'unconfigured' | 'needs-permission' | 'connected'

/** 全局单例：整个应用共享同一个已授权目录（句柄在 IndexedDB 中按 userId 隔离） */
const handle = shallowRef<LocalDirHandle | null>(null)
const permission = ref<PermissionState>('denied')
const userId = ref<string | null>(null)

/* 双向同步状态 */
const syncing = ref(false)
const lastSummary = ref<SyncSummary | null>(null)
const conflicts = ref<StoredConflict[]>([])
const autoPull = ref(true)

function currentUserId(): string | null {
  if (userId.value) {
    return userId.value
  }
  try {
    userId.value = useAuthStore().user?.user_id ?? null
  } catch {
    /* 单测/非 Pinia 环境下退化为未登录 */
  }
  return userId.value
}

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

async function init(id?: string): Promise<void> {
  const resolved = id ?? currentUserId()
  if (resolved && userId.value && userId.value !== resolved) {
    // 账号切换：先停掉上一个账号的监听并丢弃其句柄，避免串目录
    await disconnect()
  }
  if (resolved) {
    userId.value = resolved
  }
  if (!isLocalWorkspaceSupported() || handle.value) {
    return
  }
  const uid = userId.value
  const stored = uid ? await loadRootHandle(uid) : null
  const effective = stored ?? (await loadStoredHandle())
  if (!effective) {
    return
  }
  handle.value = effective
  permission.value = await queryPermission(effective)
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
  const uid = currentUserId()
  try {
    if (uid) {
      await storeRootHandle(uid, picked)
    } else {
      await storeHandle(picked)
    }
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
  workspaceWatcher.stop()
  handle.value = null
  permission.value = 'denied'
  lastSummary.value = null
  conflicts.value = []
  const uid = userId.value
  userId.value = null
  try {
    if (uid) {
      await clearRootHandle(uid)
    }
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

function connected(): boolean {
  return status.value === 'connected' && handle.value !== null
}

function categoryNameFor(categoryId: string | null): string | null {
  return categoryId ? categoryNameOf(categoryId) : null
}

/**
 * 会议的本地存储路径段：「授权目录/<分类名?>/<会议名>/」。
 * 分类可选：有分类放分类文件夹下，无分类直接平铺（分类与会议可同级）。
 * 优先使用创建时持久化的路径（改名后与磁盘保持一致），否则按当前分类/标题推导。
 * categoryId 显式传入时以它为准（创建/编辑流程刚写入归属，立即可用）。
 */
function meetingSegmentsOf(meetingId: string, title: string, categoryId?: string | null): string[] {
  const categoryName =
    categoryId !== undefined ? categoryNameFor(categoryId) : categoryNameOf(categoryOf(meetingId))
  const segments = categoryName ? [sanitizeFolderName(categoryName)] : []
  segments.push(sanitizeFolderName(title))
  return segments
}

async function storedMeetingSegments(meetingId: string, title: string): Promise<string[]> {
  try {
    const stored = await loadMeetingRoot(meetingId)
    if (stored && stored.length > 0) {
      return stored
    }
  } catch {
    /* 读取失败走推导 */
  }
  return meetingSegmentsOf(meetingId, title)
}

/**
 * 把会议相关文件镜像写入本地会议文件夹。
 * 未授权时返回 skipped 静默降级，绝不影响主流程。
 */
async function mirrorMeetingFile(options: MirrorMeetingFileOptions): Promise<MirrorResult> {
  if (!connected()) {
    return 'skipped'
  }
  try {
    const title = options.meetingTitle ?? (await resolveMeetingTitle(options.meetingId))
    const segments = await storedMeetingSegments(options.meetingId, title)
    const content =
      typeof options.content === 'string'
        ? new Blob([options.content], { type: 'text/plain;charset=utf-8' })
        : options.content
    await writeBlobToPath(
      handle.value as LocalDirHandle,
      segments,
      sanitizeFolderName(options.fileName),
      content,
    )
    return 'written'
  } catch (caught) {
    console.warn('[local-workspace] 本地镜像写入失败', caught)
    return 'failed'
  }
}

/**
 * 把用户确认后的纪要写入本地会议文件夹「会议纪要_<会议标题>.md」。
 * 确认版文件名固定：同一版本重复确认覆盖写入，不产生草稿版本残留。
 * 未连接本地文件夹时直接跳过，不发起会议标题解析请求。
 */
async function mirrorConfirmedMinutes(
  meetingId: string,
  content: string,
  meetingTitle?: string,
): Promise<MirrorResult> {
  if (!connected()) {
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

/* ===== 目录结构同步（项目 ↔ 本地文件夹） ===== */

/** 新建分类 → 本地授权目录创建 <分类名>/ 文件夹 */
async function syncCategoryFolder(categoryName: string): Promise<void> {
  if (!connected()) {
    return
  }
  try {
    await ensureLocalDir(handle.value as LocalDirHandle, [sanitizeFolderName(categoryName)])
  } catch (caught) {
    console.warn('[local-workspace] 分类文件夹创建失败', caught)
  }
}

/**
 * 新建会议 → 本地创建 <分类名?>/<会议名>/ 并持久化路径映射。
 * 分类可选：未选分类时会议文件夹直接位于授权目录下。
 */
async function createMeetingLocal(
  meetingId: string,
  title: string,
  categoryId: string | null,
): Promise<void> {
  if (!connected()) {
    return
  }
  const segments = meetingSegmentsOf(meetingId, title, categoryId)
  try {
    await ensureLocalDir(handle.value as LocalDirHandle, segments)
    await storeMeetingRoot(meetingId, segments)
  } catch (caught) {
    console.warn('[local-workspace] 会议文件夹创建失败', caught)
  }
}

/**
 * 编辑会议（改名/换分类）→ 本地文件夹同步迁移。
 * FSA 无原生 rename：新目录 + 复制文件 + 删除旧目录；失败保留旧目录降级。
 */
async function syncMeetingLocal(
  meetingId: string,
  title: string,
  categoryId: string | null,
): Promise<void> {
  if (!connected()) {
    return
  }
  const root = handle.value as LocalDirHandle
  const target = meetingSegmentsOf(meetingId, title, categoryId)
  try {
    const stored = await loadMeetingRoot(meetingId)
    if (stored && stored.join('/') !== target.join('/')) {
      // 分类可选：分类变化时会议文件夹在 <分类>/<会议> 与 <会议> 之间迁移
      const source = stored.length > 0 ? stored : meetingSegmentsOf(meetingId, title, categoryId)
      await moveDirPath(root, source, target)
    } else if (!stored) {
      await ensureLocalDir(root, target)
    }
    await storeMeetingRoot(meetingId, target)
  } catch (caught) {
    console.warn('[local-workspace] 会议文件夹迁移失败（保留原文件夹）', caught)
  }
}

/** 删除会议 → 同步删除本地会议文件夹（含其下文件） */
async function deleteMeetingLocal(meetingId: string, title: string): Promise<void> {
  if (!connected()) {
    return
  }
  const root = handle.value as LocalDirHandle
  try {
    const segments = await storedMeetingSegments(meetingId, title)
    await removeDirPath(root, segments)
  } catch (caught) {
    console.warn('[local-workspace] 会议文件夹删除失败', caught)
  }
  try {
    await clearMeetingRoot(meetingId)
  } catch {
    /* 映射清理失败不影响主流程 */
  }
}

/**
 * 删除分类 → 分类下会议的本地文件夹整体上移一层（<分类>/<会议> → <会议>），
 * 与「会议归入未分类」的数据变化保持一致。
 */
async function demoteCategoryLocal(
  categoryName: string,
  meetings: { meetingId: string; title: string }[],
): Promise<void> {
  if (!connected()) {
    return
  }
  const root = handle.value as LocalDirHandle
  const categoryFolder = sanitizeFolderName(categoryName)
  for (const meeting of meetings) {
    try {
      const stored = await loadMeetingRoot(meeting.meetingId)
      const source =
        stored && stored.length > 0 ? stored : meetingSegmentsOf(meeting.meetingId, meeting.title)
      if (source[0] !== categoryFolder || source.length < 2) {
        continue
      }
      const target = source.slice(1)
      await moveDirPath(root, source, target)
      await storeMeetingRoot(meeting.meetingId, target)
    } catch (caught) {
      console.warn('[local-workspace] 分类降级迁移失败（保留原文件夹）', caught)
    }
  }
}

/* ===== 双向同步：对账入口与确认式回写 ===== */

async function buildSyncContext(
  meetingId: string,
  meetingTitle?: string,
): Promise<RunSyncContext | null> {
  const uid = userId.value
  if (!connected() || !uid) {
    return null
  }
  const title = meetingTitle || (await resolveMeetingTitle(meetingId))
  const meetingRoot = await storedMeetingSegments(meetingId, title)
  return {
    userId: uid,
    meetingId,
    meetingTitle: title,
    root: handle.value as LocalDirHandle,
    meetingRoot,
  }
}

/** 立即对账一次：只自动执行安全动作，回写/删除留给用户确认 */
async function syncNow(meetingId: string, meetingTitle?: string): Promise<SyncSummary | null> {
  const ctx = await buildSyncContext(meetingId, meetingTitle)
  if (!ctx || syncing.value) {
    return null
  }
  syncing.value = true
  try {
    const result = await runSync(ctx, { autoPull: autoPull.value })
    lastSummary.value = result.summary
    if (userId.value) {
      conflicts.value = await loadConflicts(userId.value, ctx.meetingId)
    }
    return result.summary
  } catch (caught) {
    console.warn('[local-workspace] 同步失败', caught)
    return null
  } finally {
    syncing.value = false
  }
}

/** 用户确认后的回写；乐观锁失败（409）会抛给调用方转成冲突展示 */
async function confirmPush(
  meetingId: string,
  action: Parameters<typeof executeConfirmedPush>[0]['action'],
  payload: { file?: File; text?: string; expectedUpdatedAt?: string; expectedVersion?: number },
  meetingTitle?: string,
): Promise<boolean> {
  const ctx = await buildSyncContext(meetingId, meetingTitle)
  if (!ctx || !userId.value) {
    return false
  }
  try {
    const baseline = await executeConfirmedPush({ ctx, action, ...payload })
    if (baseline) {
      await saveBaselineFor(userId.value, ctx.meetingId, baseline)
    }
    return true
  } catch (caught) {
    console.warn('[local-workspace] 回写失败', caught)
    return false
  }
}

/** 用户处理完冲突后移除记录 */
async function resolveConflict(conflictId: string): Promise<void> {
  const uid = userId.value
  if (!uid) {
    return
  }
  await resolveStoredConflict(uid, conflictId)
  conflicts.value = conflicts.value.filter((item) => item.conflictId !== conflictId)
}

/** 是否在同步时自动拉取远端更新（只覆盖本地未修改的文件） */
async function setAutoPull(enabled: boolean): Promise<void> {
  autoPull.value = enabled
  const uid = userId.value
  if (!uid) {
    return
  }
  try {
    const prefs = await loadPrefs(uid)
    await savePrefs(uid, { ...prefs, autoPull: enabled })
  } catch {
    /* 偏好写入失败不影响本次会话 */
  }
}

/** 取该会议的同步基线，供面板展示「已同步/待处理」 */
async function loadMeetingBaselines(meetingId: string) {
  const uid = userId.value
  if (!uid) {
    return []
  }
  return loadBaselines(uid, meetingId)
}

export function useLocalWorkspace() {
  return {
    status,
    directoryName,
    rootHandle: handle,
    syncing,
    lastSummary,
    conflicts,
    autoPull,
    init,
    connect,
    restore,
    disconnect,
    syncNow,
    confirmPush,
    resolveConflict,
    setAutoPull,
    loadMeetingBaselines,
    mirrorMeetingFile,
    mirrorConfirmedMinutes,
    storedMeetingSegments,
    meetingSegmentsOf,
    syncCategoryFolder,
    createMeetingLocal,
    syncMeetingLocal,
    deleteMeetingLocal,
    demoteCategoryLocal,
    listSubdirs,
  }
}
