/**
 * 三方对账（本地快照 / 远端快照 / 上次同步基线）的纯函数实现。
 *
 * 原则（D-33）：
 * 1. 非破坏式：覆盖本地、回写远端、删除任何一端都必须由用户确认（进 prompts，不进 actions）；
 * 2. 双改不覆盖：本地与远端都变化时进 conflicts，保留两侧；
 * 3. 删除不传播：一端删除绝不自动删另一端，只产生待确认动作或墓碑；
 * 4. 幂等：同一状态反复对账，结果稳定不变。
 */

import type {
  LocalEntry,
  RemoteEntry,
  SyncAction,
  SyncBaseline,
  SyncConflict,
  SyncPlan,
  WorkspaceCategory,
} from '@/types/localWorkspace'

export interface ReconcileInput {
  meetingId: string
  baselines: SyncBaseline[]
  locals: LocalEntry[]
  remotes: RemoteEntry[]
  /** 允许把本地新增推送为远端新增（默认由用户确认后执行） */
  allowPushCreate?: boolean
  /** 允许把本地修改回写远端 */
  allowPushUpdate?: boolean
  /** 允许删除本地文件（远端删除后的收尾） */
  allowDeleteLocal?: boolean
}

/* ============================================================
 * 分类：决定文件的同步方向与可否回写
 * ============================================================ */

const MATERIAL_EXTENSIONS = new Set(['pdf', 'docx', 'txt'])
const AUDIO_EXTENSIONS = new Set(['mp3', 'wav', 'm4a', 'webm'])

export function categorize(relPath: string): WorkspaceCategory {
  const name = relPath.split('/').pop() ?? relPath
  const ext = (name.split('.').pop() ?? '').toLowerCase()
  const lower = name.toLowerCase()

  if (lower === '会议信息.json' || lower.endsWith('-会议纪要.docx') || lower.endsWith('汇总.md')) {
    return 'derived'
  }
  if (relPath.startsWith('记录/') || lower.startsWith('会议记录')) {
    return 'record'
  }
  if (relPath.startsWith('行动项/')) {
    return 'action_item'
  }
  if (relPath.startsWith('未解决问题/')) {
    return 'issue'
  }
  if (relPath.startsWith('纪要/') || lower.startsWith('会议纪要')) {
    return 'minutes'
  }
  if (relPath.startsWith('音频/') || AUDIO_EXTENSIONS.has(ext)) {
    return 'audio'
  }
  if (MATERIAL_EXTENSIONS.has(ext)) {
    return 'material'
  }
  return 'derived'
}

/** 是否可作为「本地新增 → 远端新增」回写 */
function canPushCreate(category: WorkspaceCategory): boolean {
  return (
    category === 'material' ||
    category === 'record' ||
    category === 'action_item' ||
    category === 'issue'
  )
}

/** 是否支持「本地修改 → 远端修改」回写 */
function canPushUpdate(category: WorkspaceCategory): boolean {
  return (
    category === 'minutes' ||
    category === 'record' ||
    category === 'action_item' ||
    category === 'issue'
  )
}

/* ============================================================
 * 变化判定
 * ============================================================ */

function localChanged(entry: LocalEntry, baseline: SyncBaseline): boolean {
  // 廉价路径：size 与 mtime 都没动，视为未变化
  if (entry.size === baseline.localSize && entry.lastModified === baseline.localMtime) {
    return false
  }
  // size/mtime 变了但 hash 相同（例如 touch），仍视为未变化
  if (baseline.localHash && entry.hash) {
    return entry.hash !== baseline.localHash
  }
  return true
}

function remoteChanged(remote: RemoteEntry, baseline: SyncBaseline): boolean {
  return remote.updatedAt !== baseline.remoteUpdatedAt || remote.version !== baseline.remoteVersion
}

/**
 * 同名条目判重：本地文件内容哈希与远端正文哈希一致时视为同一份内容，
 * 只建立基线、不重复导入。二进制条目不带正文哈希，按冲突处理。
 */
function sameContent(entry: LocalEntry, remote: RemoteEntry): boolean {
  if (remote.contentHash === undefined || remote.contentHash === null) {
    return false
  }
  return entry.hash === remote.contentHash
}

/* ============================================================
 * 对账主流程
 * ============================================================ */

export function reconcile(input: ReconcileInput): SyncPlan {
  const { baselines, locals, remotes } = input
  const allowPushCreate = input.allowPushCreate !== false
  const allowPushUpdate = input.allowPushUpdate !== false
  const allowDeleteLocal = input.allowDeleteLocal === true

  const actions: SyncAction[] = []
  const prompts: SyncAction[] = []
  const conflicts: SyncConflict[] = []
  let noop = 0

  const localByPath = new Map(locals.map((item) => [item.relPath, item]))
  const remoteById = new Map(remotes.map((item) => [item.remoteId, item]))
  // 远端 name 即「相对会议根的路径」，与本地 relPath 对齐
  const remoteByPath = new Map(remotes.map((item) => [item.name, item]))

  const seenPaths = new Set<string>()

  /* ---------- 1. 有基线的条目：判定谁改了 ---------- */
  for (const baseline of baselines) {
    const path = baseline.relPath
    seenPaths.add(path)
    const local = localByPath.get(path) ?? null
    const remote = remoteById.get(baseline.remoteId) ?? null

    // 双方都已删除：清理基线
    if (!local && !remote) {
      actions.push({
        kind: 'adopt',
        relPath: path,
        category: baseline.category,
        remoteId: baseline.remoteId,
        reason: '两端均已删除，清理同步基线',
      })
      continue
    }

    // 本地删除、远端仍在
    if (!local && remote) {
      if (baseline.deleteIntent === 'local-only') {
        noop += 1
        continue
      }
      if (remoteChanged(remote, baseline)) {
        conflicts.push({
          relPath: path,
          category: baseline.category,
          remoteId: baseline.remoteId,
          kind: 'delete-vs-modify',
          localUpdatedAt: baseline.localDeletedAt ?? null,
          remoteUpdatedAt: remote.updatedAt,
          detail: '本地已删除，但远端同时被修改',
        })
        continue
      }
      prompts.push({
        kind: 'delete-remote',
        relPath: path,
        category: baseline.category,
        remoteId: baseline.remoteId,
        reason: '检测到本地删除，等待确认是否同步删除服务端',
      })
      continue
    }

    // 远端删除、本地仍在
    if (local && !remote) {
      if (localChanged(local, baseline)) {
        conflicts.push({
          relPath: path,
          category: baseline.category,
          remoteId: baseline.remoteId,
          kind: 'delete-vs-modify',
          localUpdatedAt: new Date(local.lastModified).toISOString(),
          remoteUpdatedAt: baseline.remoteDeletedAt ?? null,
          detail: '服务端已删除，但本地同时被修改',
        })
        continue
      }
      if (allowDeleteLocal) {
        prompts.push({
          kind: 'delete-local',
          relPath: path,
          category: baseline.category,
          remoteId: baseline.remoteId,
          reason: '服务端已删除该条目，等待确认是否删除本地副本',
        })
      } else {
        prompts.push({
          kind: 'adopt',
          relPath: path,
          category: baseline.category,
          remoteId: baseline.remoteId,
          reason: '服务端已删除，本地副本保留为孤立文件',
        })
      }
      continue
    }

    // 两端都在
    const localDiff = local ? localChanged(local, baseline) : true
    const remoteDiff = remote ? remoteChanged(remote, baseline) : true

    if (!localDiff && !remoteDiff) {
      noop += 1
      continue
    }
    if (localDiff && !remoteDiff) {
      if (!allowPushUpdate || !canPushUpdate(baseline.category)) {
        // 派生文件或不支持回写的分类：只提示，不覆盖远端
        prompts.push({
          kind: 'adopt',
          relPath: path,
          category: baseline.category,
          remoteId: baseline.remoteId,
          reason: '本地已修改，但该类型不支持回写服务端',
        })
        continue
      }
      prompts.push({
        kind: 'push-update',
        relPath: path,
        category: baseline.category,
        remoteId: baseline.remoteId,
        reason: '检测到本地修改，等待确认后回写服务端',
      })
      continue
    }
    if (!localDiff && remoteDiff) {
      actions.push({
        kind: 'pull-update',
        relPath: path,
        category: baseline.category,
        remoteId: baseline.remoteId,
        reason: '服务端已更新，本地未修改，安全拉取',
      })
      continue
    }
    conflicts.push({
      relPath: path,
      category: baseline.category,
      remoteId: baseline.remoteId,
      kind: 'both-modified',
      localUpdatedAt: local ? new Date(local.lastModified).toISOString() : null,
      remoteUpdatedAt: remote?.updatedAt ?? null,
      detail: '两端同时修改，需选择保留版本',
    })
  }

  /* ---------- 2. 无基线的本地条目 ---------- */
  for (const local of locals) {
    if (seenPaths.has(local.relPath)) {
      continue
    }
    const remote = remoteByPath.get(local.relPath) ?? null
    const category = categorize(local.relPath)

    if (remote) {
      if (sameContent(local, remote)) {
        actions.push({
          kind: 'adopt',
          relPath: local.relPath,
          category,
          remoteId: remote.remoteId,
          reason: '内容一致，建立同步基线',
        })
      } else {
        conflicts.push({
          relPath: local.relPath,
          category,
          remoteId: remote.remoteId,
          kind: 'same-name',
          localUpdatedAt: new Date(local.lastModified).toISOString(),
          remoteUpdatedAt: remote.updatedAt,
          detail: '本地与服务端存在同名但内容不同的条目',
        })
      }
      continue
    }

    if (!allowPushCreate || !canPushCreate(category)) {
      noop += 1
      continue
    }
    prompts.push({
      kind: 'push-create',
      relPath: local.relPath,
      category,
      remoteId: null,
      reason: '检测到本地新文件，等待确认后导入服务端',
    })
  }

  /* ---------- 3. 无基线的远端条目：直接拉取 ---------- */
  for (const remote of remotes) {
    const matched = baselines.some((item) => item.remoteId === remote.remoteId)
    if (matched) {
      continue
    }
    const local = localByPath.get(remote.name) ?? null
    if (local) {
      // 与上面「无基线 + 同名」分支重合，避免重复动作
      continue
    }
    actions.push({
      kind: 'pull-create',
      relPath: remote.name,
      category: categorize(remote.name),
      remoteId: remote.remoteId,
      reason: '服务端新增条目，拉取到本地',
    })
  }

  return { actions, prompts, conflicts, noop }
}
