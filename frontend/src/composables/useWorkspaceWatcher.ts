/**
 * 本地工作区的变更监听与限流（D-33）。
 *
 * 分层策略：
 * - L1 事件驱动：FileSystemObserver（支持时优先，开销最低）；
 * - L2 轻量轮询：30s 一次，仅在页面可见时运行；
 * - L3 生命周期：visibility / focus / pageshow / online 恢复时做一次增量扫描。
 *
 * 限流：事件去抖 1.5s、合并窗口 2s、单会议最小同步间隔 10s、
 * 事件风暴（10s 内超过阈值）自动转为「等 5s 后全量扫一次」。
 */

import { onScopeDispose, ref } from 'vue'

import {
  isLocalWorkspaceSupported,
  watchDirectory,
  type DirectoryWatcher,
  type LocalDirHandle,
} from '@/utils/localFileSystem'

const DEBOUNCE_MS = 1500
const MIN_SYNC_INTERVAL_MS = 10_000
const POLL_MS = 30_000
const PERMISSION_POLL_MS = 60_000
const BURST_THRESHOLD = 100
const BURST_WINDOW_MS = 10_000
const BURST_SETTLE_MS = 5000

export interface WatcherHandlers {
  /** 需要重新对账（reason 仅用于日志） */
  onScanNeeded: (reason: string) => void
  /** 权限状态可能变化，需要重新 queryPermission */
  onPermissionProbe: () => void
  /** 页面恢复可见/重新聚焦 */
  onResume: () => void
  /** 网络状态变化 */
  onOnlineChange: (online: boolean) => void
}

export interface WorkspaceWatcher {
  start: (handle: LocalDirHandle, handlers: WatcherHandlers) => void
  stop: () => void
  /** 立即触发一次（绕过去抖，但仍受最小间隔约束） */
  kick: (reason: string) => void
  running: boolean
  mode: 'observer' | 'polling' | 'idle'
}

function createWatcher(): WorkspaceWatcher {
  const running = ref(false)
  const mode = ref<'observer' | 'polling' | 'idle'>('idle')

  let directoryWatcher: DirectoryWatcher | null = null
  let handlers: WatcherHandlers | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let mergeTimer: ReturnType<typeof setTimeout> | null = null
  let permissionTimer: ReturnType<typeof setInterval> | null = null
  let lastSyncAt = 0
  let burstCount = 0
  let burstWindowStart = 0

  function clearTimers(): void {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (mergeTimer) {
      clearTimeout(mergeTimer)
      mergeTimer = null
    }
    if (permissionTimer) {
      clearInterval(permissionTimer)
      permissionTimer = null
    }
  }

  function flush(reason: string): void {
    const now = Date.now()
    if (now - lastSyncAt < MIN_SYNC_INTERVAL_MS) {
      // 太快了：把请求并入合并窗口，避免短时间多次改动反复触发
      if (!mergeTimer) {
        mergeTimer = setTimeout(
          () => {
            mergeTimer = null
            flush(reason)
          },
          MIN_SYNC_INTERVAL_MS - (now - lastSyncAt),
        )
      }
      return
    }
    lastSyncAt = now
    burstCount = 0
    handlers?.onScanNeeded(reason)
  }

  function schedule(reason: string): void {
    if (!handlers) {
      return
    }
    // 事件风暴：短时间大量变更，等稳定后一次性全量扫描
    const now = Date.now()
    if (now - burstWindowStart > BURST_WINDOW_MS) {
      burstWindowStart = now
      burstCount = 0
    }
    burstCount += 1
    if (burstCount > BURST_THRESHOLD) {
      if (!mergeTimer) {
        mergeTimer = setTimeout(() => {
          mergeTimer = null
          flush('burst')
        }, BURST_SETTLE_MS)
      }
      return
    }

    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      flush(reason)
    }, DEBOUNCE_MS)
  }

  function onVisibility(): void {
    if (document.visibilityState === 'visible') {
      handlers?.onResume()
      schedule('resume')
    }
  }

  function onOnline(): void {
    handlers?.onOnlineChange(navigator.onLine)
    if (navigator.onLine) {
      schedule('online')
    }
  }

  function start(handle: LocalDirHandle, next: WatcherHandlers): void {
    if (!isLocalWorkspaceSupported()) {
      return
    }
    stop()
    handlers = next
    running.value = true

    directoryWatcher = watchDirectory(handle, () => schedule('fs-change'), {
      pollMs: POLL_MS,
    })
    mode.value = directoryWatcher.kind

    // 页面隐藏时轮询无意义；visibility 恢复时再触发一次
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('focus', onVisibility)
    window.addEventListener('pageshow', onVisibility)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOnline)

    permissionTimer = setInterval(() => {
      if (document.visibilityState === 'visible') {
        handlers?.onPermissionProbe()
      }
    }, PERMISSION_POLL_MS)
  }

  function stop(): void {
    directoryWatcher?.disconnect()
    directoryWatcher = null
    clearTimers()
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('focus', onVisibility)
    window.removeEventListener('pageshow', onVisibility)
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOnline)
    handlers = null
    running.value = false
    mode.value = 'idle'
    lastSyncAt = 0
    burstCount = 0
  }

  return {
    start,
    stop,
    kick: (reason: string) => schedule(reason),
    get running() {
      return running.value
    },
    get mode() {
      return mode.value
    },
  }
}

/** 全局单例：整个应用只保留一套监听器，避免多组件重复扫描 */
export const workspaceWatcher = createWatcher()

export function useWorkspaceWatcher(): WorkspaceWatcher {
  onScopeDispose(() => {
    /* 组件卸载不停止全局监听：由 useLocalWorkspace 的账号切换负责生命周期 */
  })
  return workspaceWatcher
}
