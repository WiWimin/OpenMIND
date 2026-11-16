/**
 * 本地工作区双向同步的共享类型（D-33）。
 *
 * 设计要点：
 * - 同步基线（baseline）是「上次成功同步时两端的状态」，冲突判定必须三方比对；
 * - 删除必须显式表达意图（deleteIntent），任何一端的删除都不自动传播；
 * - 冲突只记录、不覆盖，交由用户选择版本。
 */

/** 会议工作区内的内容分类；derived 为只导出的派生文件 */
export type WorkspaceCategory =
  'material' | 'minutes' | 'record' | 'action_item' | 'issue' | 'audio' | 'derived'

/** 删除意图：pending=等待用户确认，local-only=仅本地移除，propagate=已确认删除远端 */
export type DeleteIntent = 'pending' | 'local-only' | 'propagate'

export type WorkspaceStatus =
  'unsupported' | 'unconfigured' | 'needs-permission' | 'connected' | 'missing' | 'blocked'

/** 同步基线：上次成功同步时的两端快照 */
export interface SyncBaseline {
  relPath: string
  category: WorkspaceCategory
  remoteId: string
  localSize: number
  localMtime: number
  /** sha256:...；文件过大或环境不支持时为 null（退回 size+mtime 判定） */
  localHash: string | null
  remoteUpdatedAt: string
  remoteVersion: number | null
  syncedAt: string
  localDeletedAt?: string
  remoteDeletedAt?: string
  deleteIntent?: DeleteIntent
  /** 远端已删除、本地保留的孤立文件 */
  orphan?: boolean
}

/** 本地文件扫描结果 */
export interface LocalEntry {
  relPath: string
  name: string
  ext: string
  size: number
  lastModified: number
  hash?: string | null
}

/** 远端条目快照 */
export interface RemoteEntry {
  category: WorkspaceCategory
  remoteId: string
  /** 相对会议根的路径（与 LocalEntry.relPath 对齐） */
  name: string
  updatedAt: string
  version: number | null
  size: number | null
  /** 结构化条目的正文，用于本地修改检测（二进制为 undefined） */
  content?: string
  /** 结构化条目的正文哈希，用于与本地文件判重 */
  contentHash?: string | null
}

export type SyncActionKind =
  | 'pull-create'
  | 'pull-update'
  | 'push-create'
  | 'push-update'
  | 'delete-local'
  | 'delete-remote'
  | 'adopt'

export interface SyncAction {
  kind: SyncActionKind
  relPath: string
  category: WorkspaceCategory
  remoteId: string | null
  /** 人类可读的判定原因，直接进同步日志 */
  reason: string
}

export type SyncConflictKind =
  'both-modified' | 'same-name' | 'delete-vs-modify' | 'derived-modified'

export interface SyncConflict {
  relPath: string
  category: WorkspaceCategory
  remoteId: string | null
  kind: SyncConflictKind
  localUpdatedAt: string | null
  remoteUpdatedAt: string | null
  detail: string
}

export interface SyncPlan {
  /** 可直接执行的安全动作（拉取/采纳） */
  actions: SyncAction[]
  /** 需要用户确认的破坏性动作（回写、删除） */
  prompts: SyncAction[]
  conflicts: SyncConflict[]
  /** 无需动作的条目数 */
  noop: number
}

export interface SyncSummary {
  meetingId: string
  startedAt: string
  finishedAt: string
  pulled: number
  pushed: number
  deleted: number
  skipped: number
  conflicts: number
  failed: number
}

export type SyncEventType =
  | 'scan'
  | 'detected-add'
  | 'detected-modify'
  | 'detected-delete'
  | 'pull'
  | 'push-create'
  | 'push-update'
  | 'delete-local'
  | 'delete-remote'
  | 'conflict-open'
  | 'conflict-resolve'
  | 'skip'
  | 'error'
  | 'recover'

export interface SyncEvent {
  eventId: string
  syncId: string
  meetingId: string
  type: SyncEventType
  category?: WorkspaceCategory
  relPath?: string
  remoteId?: string
  result: 'ok' | 'failed' | 'skipped' | 'conflict'
  errorCode?: string
  message?: string
  at: string
}

/** 同步运行记录：用于中断恢复与代际校验 */
export interface SyncRun {
  syncId: string
  meetingId: string
  generation: number
  startedAt: string
  finishedAt?: string
  status: 'running' | 'done' | 'failed' | 'interrupted'
}

export type SyncActionPhase = 'planned' | 'in-flight' | 'succeeded' | 'committed' | 'failed'

/** 单个同步动作的执行流水：崩溃后据此判断是否需要重做 */
export interface SyncActionRecord {
  actionId: string
  syncId: string
  meetingId: string
  relPath: string
  kind: SyncActionKind
  phase: SyncActionPhase
  /** 创建类操作的幂等键，重试复用同一值 */
  clientOpId?: string
  error?: string
  at: string
}

/** 被忽略的路径规则（临时文件/缓存/日志） */
export interface WorkspacePrefs {
  autoPull: boolean
  /** 本地新增文件自动导入（默认关闭：上传会触发解析/索引/转写） */
  autoImport: boolean
  /** 本地修改自动回写（默认关闭：必须弹窗确认） */
  autoPushEdits: boolean
  watchEnabled: boolean
}
