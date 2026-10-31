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
  values: () => AsyncIterableIterator<{ kind: 'file' | 'directory'; name: string }>
  getDirectoryHandle: (
    name: string,
    options?: { create?: boolean },
  ) => Promise<LocalDirHandle>
  getFileHandle: (
    name: string,
    options?: { create?: boolean },
  ) => Promise<LocalFileHandle>
  queryPermission: (descriptor: { mode: 'readwrite' }) => Promise<PermissionState>
  requestPermission: (descriptor: { mode: 'readwrite' }) => Promise<PermissionState>
}

export interface LocalFileHandle {
  kind: 'file'
  name: string
  createWritable: () => Promise<{
    write: (data: BlobPart) => Promise<void>
    close: () => Promise<void>
  }>
}

interface PickerWindow extends Window {
  showDirectoryPicker?: (options?: { mode?: 'read' | 'readwrite' }) => Promise<LocalDirHandle>
}

const DB_NAME = 'openmind-workspace'
const DB_VERSION = 1
const STORE_NAME = 'handles'
const HANDLE_KEY = 'root-directory'

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
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME)
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
  const db = await openDb()
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode)
    const request = run(tx.objectStore(STORE_NAME))
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB 操作失败'))
    tx.oncomplete = () => db.close()
  })
}

export async function loadStoredHandle(): Promise<LocalDirHandle | null> {
  if (!isLocalWorkspaceSupported()) {
    return null
  }
  try {
    const handle = await withStore<LocalDirHandle | undefined>('readonly', (store) =>
      store.get(HANDLE_KEY) as IDBRequest<LocalDirHandle | undefined>,
    )
    return handle ?? null
  } catch {
    return null
  }
}

export async function storeHandle(handle: LocalDirHandle): Promise<void> {
  await withStore('readwrite', (store) =>
    store.put(handle, HANDLE_KEY) as IDBRequest<IDBValidKey>,
  )
}

export async function clearStoredHandle(): Promise<void> {
  await withStore('readwrite', (store) => store.delete(HANDLE_KEY) as IDBRequest<undefined>)
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

/** 逐级创建子目录并返回最深一级 */
async function ensureDirPath(
  root: LocalDirHandle,
  segments: string[],
): Promise<LocalDirHandle> {
  let dir = root
  for (const segment of segments) {
    dir = await dir.getDirectoryHandle(segment, { create: true })
  }
  return dir
}

/** 向指定子路径写入一个 Blob 文件；失败抛错由调用方决定降级策略 */
export async function writeBlobToPath(
  root: LocalDirHandle,
  segments: string[],
  fileName: string,
  content: Blob,
): Promise<void> {
  const dir = await ensureDirPath(root, segments)
  const fileHandle = await dir.getFileHandle(fileName, { create: true })
  const writable = await fileHandle.createWritable()
  await writable.write(content)
  await writable.close()
}

/** Windows / macOS 非法的文件名字符 */
export function sanitizeFolderName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '-').trim() || '未命名'
}
