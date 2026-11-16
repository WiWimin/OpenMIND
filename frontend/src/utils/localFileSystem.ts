import type {
  SyncActionRecord,
  SyncBaseline,
  SyncEvent,
  SyncRun,
  WorkspacePrefs,
} from '@/types/localWorkspace'

/**
 * 浏览器本地文件夹访问（File System Access API）的核心封装。
 *
 * 能力边界（浏览器安全限制）：
 * - 目录句柄可持久化到 IndexedDB；权限过期时用 requestPermission 一次点击恢复，无需重新选目录
 * - 所有写入均由前端发起，未授权时调用方应静默跳过
 */

export interface LocalDirHandle {
  kind: 'directory'
  name: string
  values: () => AsyncIterableIterator<{
    kind: 'file' | 'directory'
    name: string
    getFile?: () => Promise<File>
  }>
  getDirectoryHandle: (name: string, options?: { create?: boolean }) => Promise<LocalDirHandle>
  getFileHandle: (name: string, options?: { create?: boolean }) => Promise<LocalFileHandle>
  /** 删除本级目录/文件（File System Access API 原生支持，目录需 recursive） */
  removeEntry: (name: string, options?: { recursive?: boolean }) => Promise<void>
  queryPermission: (descriptor: { mode: 'readwrite' }) => Promise<PermissionState>
  requestPermission: (descriptor: { mode: 'readwrite' }) => Promise<PermissionState>
}

export interface LocalFileHandle {
  kind: 'file'
  name: string
  /** 读取文件内容（同步扫描与哈希需要） */
  getFile: () => Promise<File>
  createWritable: () => Promise<{
    write: (data: BlobPart) => Promise<void>
    close: () => Promise<void>
  }>
}

interface PickerWindow extends Window {
  showDirectoryPicker?: (options?: { mode?: 'read' | 'readwrite' }) => Promise<LocalDirHandle>
}

const DB_NAME = 'openmind-workspace'
// v2：新增双向同步所需的基线/冲突/队列/日志存储；句柄沿用 v1 的 handles 存储
const DB_VERSION = 2
const STORE_NAME = 'handles'
const HANDLE_KEY = 'root-directory'

const STORE_BASELINES = 'baselines'
const STORE_CONFLICTS = 'conflicts'
const STORE_QUEUE = 'queue'
const STORE_PREFS = 'prefs'
const STORE_RUNS = 'sync_runs'
const STORE_ACTIONS = 'sync_actions'
const STORE_EVENTS = 'sync_events'

const SYNC_STORES = [
  STORE_BASELINES,
  STORE_CONFLICTS,
  STORE_QUEUE,
  STORE_PREFS,
  STORE_RUNS,
  STORE_ACTIONS,
  STORE_EVENTS,
] as const

type SyncStoreName = (typeof SYNC_STORES)[number]

export function isLocalWorkspaceSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof (window as PickerWindow).showDirectoryPicker === 'function'
  )
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
      for (const name of SYNC_STORES) {
        if (!db.objectStoreNames.contains(name)) {
          db.createObjectStore(name)
        }
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB 打开失败'))
  })
}

async function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return withStoreName<T>(STORE_NAME, mode, run)
}

async function withStoreName<T>(
  name: string,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(name, mode)
      const request = run(tx.objectStore(name))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error ?? new Error('IndexedDB 操作失败'))
      tx.onabort = () => reject(tx.error ?? new Error('IndexedDB 事务中断'))
    })
  } finally {
    db.close()
  }
}

/** 用游标读取某个同步存储的全部键值（仅取指定前缀的键，避免跨用户串数据） */
async function readAllEntries<T>(
  name: SyncStoreName,
  userPrefix: string,
): Promise<Array<{ key: string; value: T }>> {
  const db = await openDb()
  try {
    return await new Promise<Array<{ key: string; value: T }>>((resolve, reject) => {
      const tx = db.transaction(name, 'readonly')
      const request = tx.objectStore(name).openCursor()
      const collected: Array<{ key: string; value: T }> = []
      request.onsuccess = () => {
        const cursor = request.result
        if (!cursor) {
          resolve(collected)
          return
        }
        const key = String(cursor.key)
        if (key.startsWith(userPrefix)) {
          collected.push({ key, value: cursor.value as T })
        }
        cursor.continue()
      }
      request.onerror = () => reject(request.error ?? new Error('IndexedDB 读取失败'))
    })
  } finally {
    db.close()
  }
}

export async function loadStoredHandle(): Promise<LocalDirHandle | null> {
  if (!isLocalWorkspaceSupported()) {
    return null
  }
  try {
    const handle = await withStore<LocalDirHandle | undefined>(
      'readonly',
      (store) => store.get(HANDLE_KEY) as IDBRequest<LocalDirHandle | undefined>,
    )
    return handle ?? null
  } catch {
    return null
  }
}

export async function storeHandle(handle: LocalDirHandle): Promise<void> {
  await withStore('readwrite', (store) => store.put(handle, HANDLE_KEY) as IDBRequest<IDBValidKey>)
}

export async function clearStoredHandle(): Promise<void> {
  await withStore('readwrite', (store) => store.delete(HANDLE_KEY) as IDBRequest<undefined>)
}

const MEETING_ROOT_PREFIX = 'meeting-root:'

/** 读取会议的本地存储根（路径段数组）；未设置返回 null */
export async function loadMeetingRoot(meetingId: string): Promise<string[] | null> {
  try {
    const value = await withStore<string[] | undefined>(
      'readonly',
      (store) => store.get(MEETING_ROOT_PREFIX + meetingId) as IDBRequest<string[] | undefined>,
    )
    return value ?? null
  } catch {
    return null
  }
}

/** 持久化会议的本地存储根（新建会议时的存储位置选择） */
export async function storeMeetingRoot(meetingId: string, segments: string[]): Promise<void> {
  await withStore(
    'readwrite',
    (store) => store.put(segments, MEETING_ROOT_PREFIX + meetingId) as IDBRequest<IDBValidKey>,
  )
}

/** 清除会议的本地存储根（会议删除后不再需要路径映射） */
export async function clearMeetingRoot(meetingId: string): Promise<void> {
  await withStore(
    'readwrite',
    (store) => store.delete(MEETING_ROOT_PREFIX + meetingId) as IDBRequest<undefined>,
  )
}

export async function pickDirectory(): Promise<LocalDirHandle | null> {
  const picker = (window as PickerWindow).showDirectoryPicker
  if (!picker) {
    return null
  }
  try {
    return await picker({ mode: 'readwrite' })
  } catch (caught) {
    if (isAbortError(caught)) {
      return null
    }
    throw caught
  }
}

export function isAbortError(caught: unknown): boolean {
  return (
    typeof caught === 'object' &&
    caught !== null &&
    'name' in caught &&
    (caught as { name: unknown }).name === 'AbortError'
  )
}

export async function queryPermission(handle: LocalDirHandle): Promise<PermissionState> {
  try {
    return await handle.queryPermission({ mode: 'readwrite' })
  } catch {
    return 'denied'
  }
}

export async function requestPermission(handle: LocalDirHandle): Promise<PermissionState> {
  try {
    return await handle.requestPermission({ mode: 'readwrite' })
  } catch {
    return 'denied'
  }
}

export function isWriteAllowed(state: PermissionState): boolean {
  return state === 'granted'
}

/** 逐级解析子目录；create=true 时逐级创建，false 时路径不存在抛 NotFound */
async function resolveDirPath(
  root: LocalDirHandle,
  segments: string[],
  create: boolean,
): Promise<LocalDirHandle> {
  let dir = root
  for (const segment of segments) {
    dir = await dir.getDirectoryHandle(segment, create ? { create: true } : undefined)
  }
  return dir
}

/** 逐级创建子目录并返回最深一级 */
async function ensureDirPath(root: LocalDirHandle, segments: string[]): Promise<LocalDirHandle> {
  return resolveDirPath(root, segments, true)
}

/** 列出子路径下的一级子目录名（升序，只读不创建）；路径不存在时抛 NotFound */
export async function listSubdirs(root: LocalDirHandle, segments: string[]): Promise<string[]> {
  const dir = await resolveDirPath(root, segments, false)
  const names: string[] = []
  for await (const entry of dir.values()) {
    if (entry.kind === 'directory') {
      names.push(entry.name)
    }
  }
  return names.sort((left, right) => left.localeCompare(right))
}

/** 逐级确保目录存在（创建会议时落默认会议名文件夹） */
export async function ensureLocalDir(root: LocalDirHandle, segments: string[]): Promise<void> {
  await ensureDirPath(root, segments)
}

export interface LocalFileEntry {
  name: string
  file: File
  size: number
  /** 相对会议根的 POSIX 路径（一层文件即为文件名）；同步扫描会填充 */
  relPath?: string
}

/**
 * 读取路径下第一层文件（不递归子目录，按名称排序）。
 * limit 控制最多读取的文件数；读满且仍有更多文件时 truncated=true。
 * 路径不存在时抛 NotFound（由调用方决定降级方式）。
 */
export async function readFilesAt(
  root: LocalDirHandle,
  segments: string[],
  limit = 50,
): Promise<{ files: LocalFileEntry[]; truncated: boolean }> {
  const dir = await resolveDirPath(root, segments, false)
  const files: LocalFileEntry[] = []
  let truncated = false
  for await (const entry of dir.values()) {
    if (entry.kind !== 'file' || !entry.getFile) {
      continue
    }
    if (files.length >= limit) {
      truncated = true
      break
    }
    const file = await entry.getFile()
    files.push({ name: entry.name, file, size: file.size })
  }
  files.sort((left, right) => left.name.localeCompare(right.name))
  return { files, truncated }
}

/** 向指定子路径写入一个 Blob 文件；失败抛错由调用方决定降级策略 */
export async function writeBlobToPath(
  root: LocalDirHandle,
  segments: string[],
  fileName: string,
  content: Blob,
): Promise<void> {
  // 支持 `a/b/c.txt` 形式的相对路径：目录段与文件名分别安全化
  const parts = fileName.split('/').filter((part) => part.length > 0)
  const leaf = (parts.pop() ?? fileName) as string
  const dir = await ensureDirPath(root, [...segments, ...parts])
  const fileHandle = await dir.getFileHandle(sanitizeFolderName(leaf), { create: true })
  const writable = await fileHandle.createWritable()
  await writable.write(content)
  await writable.close()
}

/**
 * 删除路径对应的目录（含其下所有内容）。
 * 路径不存在时静默返回；其余失败抛错由调用方降级。
 */
export async function removeDirPath(root: LocalDirHandle, segments: string[]): Promise<void> {
  if (segments.length === 0) {
    throw new Error('不允许删除根目录')
  }
  let parent = root
  for (const segment of segments.slice(0, -1)) {
    parent = await parent.getDirectoryHandle(segment)
  }
  await parent.removeEntry(segments[segments.length - 1] as string, { recursive: true })
}

/**
 * 把目录从旧路径搬到新路径（FSA 无原生 rename，用「复制 + 删除」模拟）。
 * - 新旧路径相同直接返回
 * - 任一文件复制失败则不删除旧目录（保留数据），抛错由调用方降级
 * - 移动只处理第一层文件（本项目会议文件夹为扁平结构）
 */
export async function moveDirPath(
  root: LocalDirHandle,
  oldSegments: string[],
  newSegments: string[],
): Promise<void> {
  if (oldSegments.length === 0 || newSegments.length === 0) {
    throw new Error('不允许操作根目录')
  }
  const oldKey = oldSegments.join('/')
  const newKey = newSegments.join('/')
  if (oldKey === newKey) {
    return
  }
  const { files } = await readFilesAt(root, oldSegments, 1000)
  // 先确保目标目录存在，再逐个复制文件
  await ensureDirPath(root, newSegments)
  for (const entry of files) {
    await writeBlobToPath(root, newSegments, entry.name, entry.file)
  }
  await removeDirPath(root, oldSegments)
}

/** Windows / macOS 非法的文件名字符 */
export function sanitizeFolderName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '-').trim() || '未命名'
}

/* ============================================================
 * 本地工作区双向同步：错误映射、忽略规则、扫描、哈希与监听（D-33）
 * 以上为 v1 能力；以下为新增能力，均不改变既有导出语义。
 * ============================================================ */

export type LocalFsErrorCode =
  'unsupported' | 'aborted' | 'denied' | 'not-found' | 'quota' | 'locked' | 'invalid-type' | 'io'

/** 统一把 DOMException 映射为可判定的错误码，供同步引擎分支处理 */
export class LocalFsError extends Error {
  readonly code: LocalFsErrorCode

  constructor(code: LocalFsErrorCode, message: string, options?: { cause?: unknown }) {
    super(message, options)
    this.name = 'LocalFsError'
    this.code = code
  }
}

const DOM_ERROR_MAP: Record<string, LocalFsErrorCode> = {
  AbortError: 'aborted',
  NotAllowedError: 'denied',
  SecurityError: 'denied',
  NotFoundError: 'not-found',
  QuotaExceededError: 'quota',
  NotReadableError: 'locked',
  InvalidStateError: 'locked',
  TypeMismatchError: 'invalid-type',
}

export function toLocalFsError(caught: unknown, fallback = '本地文件操作失败'): LocalFsError {
  if (caught instanceof LocalFsError) {
    return caught
  }
  const name =
    typeof caught === 'object' && caught !== null && 'name' in caught
      ? String((caught as { name: unknown }).name)
      : ''
  const message =
    typeof caught === 'object' && caught !== null && 'message' in caught
      ? String((caught as { message: unknown }).message)
      : ''
  return new LocalFsError(DOM_ERROR_MAP[name] ?? 'io', message || fallback, { cause: caught })
}

export function isPermissionError(caught: unknown): boolean {
  return toLocalFsError(caught).code === 'denied'
}

/* ---------- 忽略规则：临时文件 / 缓存 / 日志 / 隐藏目录 ---------- */

/** 忽略的目录名（版本库、缓存、工作区状态） */
export const IGNORED_DIRECTORIES = new Set([
  '.openmind',
  '.git',
  'node_modules',
  '__pycache__',
  '.venv',
  'dist',
  'build',
  '.idea',
  '.vscode',
  '.Trashes',
  '.Spotlight-V100',
  '.fseventsd',
])

const IGNORED_FILE_PATTERNS: RegExp[] = [
  /^~\$.*$/,
  /^\.~lock\..*#$/,
  /^\.DS_Store$/,
  /^Thumbs\.db$/i,
  /^desktop\.ini$/i,
  /^\._.*$/,
  /\.(tmp|temp|swp|swo|bak|part|partial|crdownload|download|lock|log|cache)$/i,
]

export function isIgnoredDirectory(name: string): boolean {
  return IGNORED_DIRECTORIES.has(name) || name.startsWith('.')
}

export function isIgnoredFile(name: string): boolean {
  return IGNORED_FILE_PATTERNS.some((pattern) => pattern.test(name))
}

/* ---------- 递归扫描（带预算与过滤） ---------- */

export interface ScanOptions {
  /** 最大扫描条目数，超出即中断（防止大目录拖垮同步） */
  maxEntries?: number
  /** 最大递归深度；1 表示只看一层 */
  maxDepth?: number
  /** 是否跳过临时/缓存/隐藏文件，默认跳过 */
  skipIgnored?: boolean
}

/**
 * 递归扫描目录，返回带相对路径的文件清单（按相对路径排序）。
 * 默认跳过 `.openmind`、临时文件、缓存与隐藏文件。
 */
export async function scanEntries(
  root: LocalDirHandle,
  segments: string[],
  options: ScanOptions = {},
): Promise<{ entries: LocalFileEntry[]; truncated: boolean }> {
  const maxEntries = options.maxEntries ?? 500
  const maxDepth = options.maxDepth ?? 3
  const skipIgnored = options.skipIgnored !== false
  const dir = await resolveDirPath(root, segments, false)

  const entries: LocalFileEntry[] = []
  let truncated = false

  async function walk(current: LocalDirHandle, depth: number, prefix: string): Promise<void> {
    if (truncated) {
      return
    }
    for await (const entry of current.values()) {
      if (truncated) {
        return
      }
      if (entry.kind === 'directory') {
        if (depth >= maxDepth) {
          continue
        }
        if (skipIgnored && isIgnoredDirectory(entry.name)) {
          continue
        }
        const child = await current.getDirectoryHandle(entry.name).catch(() => null)
        if (!child) {
          continue
        }
        await walk(child, depth + 1, prefix ? prefix + '/' + entry.name : entry.name)
        continue
      }
      if (!entry.getFile) {
        continue
      }
      if (skipIgnored && isIgnoredFile(entry.name)) {
        continue
      }
      if (entries.length >= maxEntries) {
        truncated = true
        return
      }
      const file = await entry.getFile()
      entries.push({
        name: entry.name,
        file,
        size: file.size,
        relPath: prefix ? prefix + '/' + entry.name : entry.name,
      })
    }
  }

  await walk(dir, 1, '')
  entries.sort((left, right) =>
    (left.relPath ?? left.name).localeCompare(right.relPath ?? right.name),
  )
  return { entries, truncated }
}

/** 读取相对路径下的文本文件（如 `.openmind/manifest.json`） */
export async function readTextAtRelPath(
  root: LocalDirHandle,
  segments: string[],
  relPath: string,
): Promise<string> {
  const parts = relPath.split('/').filter((part) => part.length > 0)
  const leaf = (parts.pop() ?? relPath) as string
  const dir = await resolveDirPath(root, [...segments, ...parts], false)
  const fileHandle = await dir.getFileHandle(sanitizeFolderName(leaf))
  return (await fileHandle.getFile()).text()
}

/** 写入相对路径下的文本文件 */
export async function writeTextAtRelPath(
  root: LocalDirHandle,
  segments: string[],
  relPath: string,
  text: string,
): Promise<void> {
  await writeBlobToPath(
    root,
    segments,
    relPath,
    new Blob([text], { type: 'text/plain;charset=utf-8' }),
  )
}

/** 删除相对路径下的文件；不存在时静默返回 */
export async function removeFileAtRelPath(
  root: LocalDirHandle,
  segments: string[],
  relPath: string,
): Promise<void> {
  const parts = relPath.split('/').filter((part) => part.length > 0)
  const leaf = (parts.pop() ?? relPath) as string
  const dir = await resolveDirPath(root, [...segments, ...parts], false)
  try {
    await dir.removeEntry(sanitizeFolderName(leaf))
  } catch (caught) {
    const error = toLocalFsError(caught)
    if (error.code === 'not-found') {
      return
    }
    throw error
  }
}

/* ---------- 内容哈希：变化检测的最终依据 ---------- */

const HASH_MAX_BYTES = 20 * 1024 * 1024

/** 文件内容哈希（sha256）；过大或环境不支持时返回 null（退回 size+mtime 判定） */
export async function hashFile(file: File): Promise<string | null> {
  if (file.size > HASH_MAX_BYTES) {
    return null
  }
  const subtle = globalThis.crypto?.subtle
  if (!subtle) {
    return null
  }
  try {
    const buffer = await file.arrayBuffer()
    const digest = await subtle.digest('SHA-256', buffer)
    const hex = [...new Uint8Array(digest)]
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('')
    return 'sha256:' + hex
  } catch {
    return null
  }
}

/** 文本内容哈希，用于结构化条目与本地文件判重 */
export async function hashText(text: string): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle
  if (!subtle) {
    return null
  }
  try {
    const digest = await subtle.digest('SHA-256', new TextEncoder().encode(text))
    const hex = [...new Uint8Array(digest)]
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('')
    return 'sha256:' + hex
  } catch {
    return null
  }
}

/* ---------- 变更观察：优先 FileSystemObserver，否则定时轮询 ---------- */

interface FsObserverInstance {
  observe: (handle: LocalDirHandle, options: { recursive: boolean }) => Promise<void>
  disconnect: () => void
}

interface FsObserverConstructor {
  new (callback: () => void): FsObserverInstance
}

export interface DirectoryWatcher {
  disconnect: () => void
  readonly kind: 'observer' | 'polling'
}

/**
 * 监听目录变化。支持 FileSystemObserver 时走事件驱动，否则按 pollMs 轮询。
 * 回调只提示「有变化」，不携带内容；由上层去抖后统一扫描。
 */
export function watchDirectory(
  handle: LocalDirHandle,
  onChange: () => void,
  options: { pollMs?: number } = {},
): DirectoryWatcher {
  const Observer = (globalThis as { FileSystemObserver?: FsObserverConstructor }).FileSystemObserver

  if (Observer) {
    const observer = new Observer(() => onChange())
    void observer.observe(handle, { recursive: true })
    return { kind: 'observer', disconnect: () => observer.disconnect() }
  }

  const timer = setInterval(() => onChange(), options.pollMs ?? 30_000)
  return { kind: 'polling', disconnect: () => clearInterval(timer) }
}

/* ---------- 按用户隔离的同步状态（句柄/基线/冲突/队列/日志/偏好） ---------- */

function userKey(userId: string, key: string): string {
  return userId + ':' + key
}

/** 句柄按用户隔离：避免同浏览器多账号串目录（v1 全局键作为迁移兜底） */
export async function loadRootHandle(userId: string): Promise<LocalDirHandle | null> {
  if (!userId || !isLocalWorkspaceSupported()) {
    return null
  }
  try {
    const stored = await withStore<LocalDirHandle | undefined>(
      'readonly',
      (store) => store.get(userKey(userId, 'root')) as IDBRequest<LocalDirHandle | undefined>,
    )
    if (stored) {
      return stored
    }
    return await adoptLegacyRoot(userId)
  } catch {
    return null
  }
}

async function adoptLegacyRoot(userId: string): Promise<LocalDirHandle | null> {
  const legacy = await withStore<LocalDirHandle | undefined>(
    'readonly',
    (store) => store.get(HANDLE_KEY) as IDBRequest<LocalDirHandle | undefined>,
  )
  if (!legacy) {
    return null
  }
  await withStore('readwrite', (store) => {
    store.delete(HANDLE_KEY)
    return store.put(legacy, userKey(userId, 'root')) as IDBRequest<IDBValidKey>
  })
  return legacy
}

export async function storeRootHandle(userId: string, handle: LocalDirHandle): Promise<void> {
  await withStore(
    'readwrite',
    (store) => store.put(handle, userKey(userId, 'root')) as IDBRequest<IDBValidKey>,
  )
}

export async function clearRootHandle(userId: string): Promise<void> {
  await withStore(
    'readwrite',
    (store) => store.delete(userKey(userId, 'root')) as IDBRequest<undefined>,
  )
}

/* ---------- 同步基线 ---------- */

export type StoredBaseline = SyncBaseline

function baselineKey(meetingId: string, relPath: string): string {
  return meetingId + ':' + relPath
}

export async function loadBaselines(userId: string, meetingId: string): Promise<StoredBaseline[]> {
  try {
    const entries = await readAllEntries<StoredBaseline>(STORE_BASELINES, userKey(userId, ''))
    return entries
      .filter((entry) => entry.key.startsWith(userKey(userId, meetingId + ':')))
      .map((entry) => entry.value)
  } catch {
    return []
  }
}

export async function saveBaselineFor(
  userId: string,
  meetingId: string,
  baseline: StoredBaseline,
): Promise<void> {
  await withStoreName(
    STORE_BASELINES,
    'readwrite',
    (store) =>
      store.put(
        baseline,
        userKey(userId, baselineKey(meetingId, baseline.relPath)),
      ) as IDBRequest<IDBValidKey>,
  )
}

export async function deleteBaselineFor(
  userId: string,
  meetingId: string,
  relPath: string,
): Promise<void> {
  await withStoreName(
    STORE_BASELINES,
    'readwrite',
    (store) =>
      store.delete(userKey(userId, baselineKey(meetingId, relPath))) as IDBRequest<undefined>,
  )
}

/* ---------- 运行 / 动作 / 事件日志 ---------- */

export type StoredRun = SyncRun

export async function saveRun(userId: string, run: StoredRun): Promise<void> {
  await withStoreName(
    STORE_RUNS,
    'readwrite',
    (store) => store.put(run, userKey(userId, run.syncId)) as IDBRequest<IDBValidKey>,
  )
}

export type StoredActionRecord = SyncActionRecord

export async function saveActionRecord(userId: string, record: StoredActionRecord): Promise<void> {
  await withStoreName(
    STORE_ACTIONS,
    'readwrite',
    (store) => store.put(record, userKey(userId, record.actionId)) as IDBRequest<IDBValidKey>,
  )
}

export async function loadActionRecords(
  userId: string,
  meetingId: string,
): Promise<StoredActionRecord[]> {
  try {
    const entries = await readAllEntries<StoredActionRecord>(STORE_ACTIONS, userKey(userId, ''))
    return entries.map((entry) => entry.value).filter((item) => item.meetingId === meetingId)
  } catch {
    return []
  }
}

export async function deleteActionRecord(userId: string, actionId: string): Promise<void> {
  await withStoreName(
    STORE_ACTIONS,
    'readwrite',
    (store) => store.delete(userKey(userId, actionId)) as IDBRequest<undefined>,
  )
}

export type StoredEvent = SyncEvent

export async function appendSyncEvent(userId: string, event: StoredEvent): Promise<void> {
  try {
    await withStoreName(
      STORE_EVENTS,
      'readwrite',
      (store) => store.put(event, userKey(userId, event.eventId)) as IDBRequest<IDBValidKey>,
    )
  } catch {
    /* 日志失败不影响主流程 */
  }
}

export async function loadSyncEvents(userId: string, meetingId: string): Promise<StoredEvent[]> {
  try {
    const entries = await readAllEntries<StoredEvent>(STORE_EVENTS, userKey(userId, ''))
    return entries
      .map((entry) => entry.value)
      .filter((item) => item.meetingId === meetingId)
      .sort((left, right) => left.at.localeCompare(right.at))
  } catch {
    return []
  }
}

/* ---------- 重试队列与冲突 ---------- */

export interface StoredQueueOp {
  queueId: string
  meetingId: string
  relPath: string
  kind: string
  clientOpId?: string
  attempts: number
  nextAttemptAt: string
  lastError?: string
  at: string
}

export async function enqueueRetry(userId: string, op: StoredQueueOp): Promise<void> {
  await withStoreName(
    STORE_QUEUE,
    'readwrite',
    (store) => store.put(op, userKey(userId, op.queueId)) as IDBRequest<IDBValidKey>,
  )
}

export async function loadRetryQueue(userId: string, meetingId: string): Promise<StoredQueueOp[]> {
  try {
    const entries = await readAllEntries<StoredQueueOp>(STORE_QUEUE, userKey(userId, ''))
    return entries
      .map((entry) => entry.value)
      .filter((item) => item.meetingId === meetingId)
      .sort((left, right) => left.nextAttemptAt.localeCompare(right.nextAttemptAt))
  } catch {
    return []
  }
}

export async function dequeueRetry(userId: string, queueId: string): Promise<void> {
  await withStoreName(
    STORE_QUEUE,
    'readwrite',
    (store) => store.delete(userKey(userId, queueId)) as IDBRequest<undefined>,
  )
}

export interface StoredConflict {
  conflictId: string
  meetingId: string
  relPath: string
  kind: string
  detail: string
  detectedAt: string
  resolved: boolean
}

export async function saveConflict(userId: string, conflict: StoredConflict): Promise<void> {
  await withStoreName(
    STORE_CONFLICTS,
    'readwrite',
    (store) => store.put(conflict, userKey(userId, conflict.conflictId)) as IDBRequest<IDBValidKey>,
  )
}

export async function loadConflicts(userId: string, meetingId: string): Promise<StoredConflict[]> {
  try {
    const entries = await readAllEntries<StoredConflict>(STORE_CONFLICTS, userKey(userId, ''))
    return entries
      .map((entry) => entry.value)
      .filter((item) => item.meetingId === meetingId)
      .sort((left, right) => right.detectedAt.localeCompare(left.detectedAt))
  } catch {
    return []
  }
}

export async function resolveConflict(userId: string, conflictId: string): Promise<void> {
  await withStoreName(
    STORE_CONFLICTS,
    'readwrite',
    (store) => store.delete(userKey(userId, conflictId)) as IDBRequest<undefined>,
  )
}

/* ---------- 偏好 ---------- */

export type StoredPrefs = WorkspacePrefs

const DEFAULT_PREFS: StoredPrefs = {
  autoPull: true,
  autoImport: false,
  autoPushEdits: false,
  watchEnabled: true,
}

export async function loadPrefs(userId: string): Promise<StoredPrefs> {
  try {
    const stored = await withStore<Partial<StoredPrefs> | undefined>(
      'readonly',
      (store) =>
        store.get(userKey(userId, 'prefs')) as IDBRequest<Partial<StoredPrefs> | undefined>,
    )
    return { ...DEFAULT_PREFS, ...(stored ?? {}) }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export async function savePrefs(userId: string, prefs: StoredPrefs): Promise<void> {
  await withStoreName(
    STORE_PREFS,
    'readwrite',
    (store) => store.put(prefs, userKey(userId, 'prefs')) as IDBRequest<IDBValidKey>,
  )
}
