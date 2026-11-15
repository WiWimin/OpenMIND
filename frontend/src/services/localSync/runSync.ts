/**
 * 同步执行器：远端快照 → 本地快照 → 三方对账 → 执行安全动作 → 记录基线/日志。
 *
 * 只自动执行「非破坏式」动作（拉取、建立基线）；
 * 回写、删除一律产出待确认项，由用户确认后执行（D-33）。
 */

import * as actionItemsApi from '@/api/actionItems'
import * as audioApi from '@/api/audio'
import * as issuesApi from '@/api/issues'
import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import * as recordsApi from '@/api/records'
import { buildManifest, writeManifest } from '@/services/localSync/manifest'
import { reconcile, type ReconcileInput } from '@/services/localSync/reconcile'
import type {
  LocalEntry,
  RemoteEntry,
  SyncAction,
  SyncBaseline,
  SyncEvent,
  SyncPlan,
  SyncSummary,
  WorkspaceCategory,
} from '@/types/localWorkspace'
import { htmlToMarkdown } from '@/utils/minutesMarkdown'
import {
  appendSyncEvent,
  deleteBaselineFor,
  dequeueRetry,
  enqueueRetry,
  hashFile,
  hashText,
  loadBaselines,
  loadRetryQueue,
  saveActionRecord,
  saveBaselineFor,
  saveRun,
  scanEntries,
  toLocalFsError,
  writeBlobToPath,
  writeTextAtRelPath,
  type LocalDirHandle,
  type LocalFileEntry,
} from '@/utils/localFileSystem'

const MAX_LIST_PAGES = 20
const PAGE_SIZE = 100

function newId(prefix: string): string {
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '')
      : `${Date.now()}${Math.floor(Math.random() * 1e9)}`
  return `${prefix}_${random}`
}

export interface RunSyncContext {
  userId: string
  meetingId: string
  meetingTitle: string
  root: LocalDirHandle
  meetingRoot: string[]
}

export interface RunSyncResult {
  summary: SyncSummary
  plan: SyncPlan
}

function makeEvent(
  ctx: RunSyncContext,
  syncId: string,
  type: SyncEvent['type'],
  result: SyncEvent['result'],
  extra: Partial<SyncEvent> = {},
): SyncEvent {
  return {
    eventId: newId('evt'),
    syncId,
    meetingId: ctx.meetingId,
    type,
    result,
    at: new Date().toISOString(),
    ...extra,
  }
}

/* ============================================================
 * 远端快照
 * ============================================================ */

async function listAll<T>(
  fetchPage: (
    page: number,
    pageSize: number,
  ) => Promise<{ items: T[]; pagination: { total_pages: number } }>,
): Promise<T[]> {
  const collected: T[] = []
  for (let page = 1; page <= MAX_LIST_PAGES; page += 1) {
    const result = await fetchPage(page, PAGE_SIZE)
    collected.push(...result.items)
    if (page >= result.pagination.total_pages) {
      break
    }
  }
  return collected
}

async function buildRemoteSnapshot(ctx: RunSyncContext): Promise<RemoteEntry[]> {
  const entries: RemoteEntry[] = []

  const materials = await listAll((page, pageSize) =>
    materialsApi.listMaterials(ctx.meetingId, { page, page_size: pageSize }),
  )
  for (const item of materials) {
    entries.push({
      category: 'material',
      remoteId: item.material_id,
      name: item.file_name,
      updatedAt: item.created_at,
      version: null,
      size: item.file_size ?? null,
    })
  }

  const minutesList = await listAll((page, pageSize) =>
    minutesApi.listMinutes(ctx.meetingId, { page, page_size: pageSize }),
  )
  // 只导出「已确认」纪要；草稿不落盘（项目规则）
  const latest = minutesList
    .filter((item) => item.status === 'confirmed')
    .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0]
  if (latest) {
    const md = htmlToMarkdown(latest.content)
    entries.push({
      category: 'minutes',
      remoteId: latest.minutes_id,
      name: `纪要/会议纪要_${ctx.meetingTitle}.md`,
      updatedAt: latest.updated_at,
      version: latest.version,
      size: md.length,
      content: md,
      contentHash: await hashText(md),
    })
  }

  const records = await listAll((page, pageSize) =>
    recordsApi.listRecords(ctx.meetingId, { page, page_size: pageSize }),
  )
  for (const item of records) {
    const stamp = item.created_at.replace(/[:T]/g, '-').slice(0, 16)
    entries.push({
      category: 'record',
      remoteId: item.record_id,
      name: `记录/会议记录_${stamp}_${item.record_id}.md`,
      updatedAt: item.updated_at,
      version: null,
      size: item.content.length,
      content: item.content,
      contentHash: await hashText(item.content),
    })
  }

  const actionItems = await listAll((page, pageSize) =>
    actionItemsApi.listActionItems(ctx.meetingId, { page, page_size: pageSize }),
  )
  for (const item of actionItems) {
    const text = actionItemToMarkdown(item)
    entries.push({
      category: 'action_item',
      remoteId: item.action_id,
      name: `行动项/行动项_${item.action_id}.md`,
      updatedAt: item.updated_at,
      version: null,
      size: text.length,
      content: text,
      contentHash: await hashText(text),
    })
  }

  const issues = await listAll((page, pageSize) =>
    issuesApi.listIssues(ctx.meetingId, { page, page_size: pageSize }),
  )
  for (const item of issues) {
    const text = issueToMarkdown(item)
    entries.push({
      category: 'issue',
      remoteId: item.issue_id,
      name: `未解决问题/问题_${item.issue_id}.md`,
      updatedAt: item.updated_at,
      version: null,
      size: text.length,
      content: text,
      contentHash: await hashText(text),
    })
  }

  return entries
}

function actionItemToMarkdown(item: {
  action_id: string
  content: string
  assignee: string | null
  due_date: string | null
  status: string
}): string {
  return [
    '<!-- openmind-sync',
    JSON.stringify({ schema: 2, category: 'action_item', remoteId: item.action_id }),
    '-->',
    '',
    '# 行动项',
    '',
    `- 内容：${item.content}`,
    `- 负责人：${item.assignee ?? '未指定'}`,
    `- 截止日期：${item.due_date ?? '未设置'}`,
    `- 状态：${item.status}（只读，修改无效）`,
    '',
  ].join('\n')
}

function issueToMarkdown(item: {
  issue_id: string
  description: string
  follow_up: string | null
  status: string
}): string {
  return [
    '<!-- openmind-sync',
    JSON.stringify({ schema: 2, category: 'issue', remoteId: item.issue_id }),
    '-->',
    '',
    '# 未解决问题',
    '',
    `- 状态：${item.status}`,
    `- 跟进：${item.follow_up ?? '无'}`,
    '',
    '## 描述',
    '',
    item.description,
    '',
  ].join('\n')
}

/* ============================================================
 * 本地快照
 * ============================================================ */

interface LocalSnapshot {
  entries: LocalEntry[]
  files: Map<string, LocalFileEntry>
  truncated: boolean
}

async function buildLocalSnapshot(ctx: RunSyncContext): Promise<LocalSnapshot> {
  const { entries, truncated } = await scanEntries(ctx.root, ctx.meetingRoot, {
    maxEntries: 500,
    maxDepth: 3,
    skipIgnored: true,
  })
  const files = new Map<string, LocalFileEntry>()
  const locals: LocalEntry[] = []
  for (const entry of entries) {
    const relPath = entry.relPath ?? entry.name
    files.set(relPath, entry)
    locals.push({
      relPath,
      name: entry.name,
      ext: (entry.name.split('.').pop() ?? '').toLowerCase(),
      size: entry.size,
      lastModified: entry.file.lastModified,
    })
  }
  return { entries: locals, files, truncated }
}

/** 只对「相对基线有变化」的文件算哈希，避免大目录全量哈希 */
async function enrichWithHashes(
  locals: LocalEntry[],
  files: Map<string, LocalFileEntry>,
  baselines: SyncBaseline[],
): Promise<void> {
  const baselineByPath = new Map(baselines.map((item) => [item.relPath, item]))
  for (const local of locals) {
    const base = baselineByPath.get(local.relPath)
    const unchanged =
      base !== undefined && local.size === base.localSize && local.lastModified === base.localMtime
    if (unchanged) {
      local.hash = base.localHash
      continue
    }
    const file = files.get(local.relPath)
    local.hash = file ? await hashFile(file.file) : null
  }
}

/* ============================================================
 * 拉取与基线写入
 * ============================================================ */

async function pullEntry(
  ctx: RunSyncContext,
  action: SyncAction,
  remote: RemoteEntry | undefined,
): Promise<void> {
  if (!remote) {
    return
  }
  if (remote.category === 'material' || remote.category === 'audio') {
    const blob =
      remote.category === 'material'
        ? await materialsApi.downloadMaterial(remote.remoteId)
        : await audioApi.downloadAudio(remote.remoteId)
    await writeBlobToPath(ctx.root, ctx.meetingRoot, action.relPath, blob)
    return
  }
  if (remote.content !== undefined) {
    await writeTextAtRelPath(ctx.root, ctx.meetingRoot, action.relPath, remote.content)
  }
}

/** 拉取完成后重新读取本地文件元数据，写入的基线必须是「拉取后的真实状态」 */
async function statAfterWrite(
  ctx: RunSyncContext,
  relPath: string,
): Promise<{ size: number; mtime: number; hash: string | null }> {
  const snapshot = await buildLocalSnapshot(ctx)
  const found = snapshot.files.get(relPath)
  if (!found) {
    return { size: 0, mtime: Date.now(), hash: null }
  }
  return {
    size: found.size,
    mtime: found.file.lastModified,
    hash: await hashFile(found.file),
  }
}

async function writeBaseline(
  ctx: RunSyncContext,
  action: SyncAction,
  remote: RemoteEntry | undefined,
  local: { size: number; mtime: number; hash: string | null },
): Promise<void> {
  if (!remote) {
    await deleteBaselineFor(ctx.userId, ctx.meetingId, action.relPath)
    return
  }
  await saveBaselineFor(ctx.userId, ctx.meetingId, {
    relPath: action.relPath,
    category: action.category,
    remoteId: remote.remoteId,
    localSize: local.size,
    localMtime: local.mtime,
    localHash: local.hash,
    remoteUpdatedAt: remote.updatedAt,
    remoteVersion: remote.version,
    syncedAt: new Date().toISOString(),
  })
}

/* ============================================================
 * 主流程
 * ============================================================ */

export async function runSync(
  ctx: RunSyncContext,
  options: { autoPull?: boolean } = {},
): Promise<RunSyncResult> {
  const syncId = newId('syn')
  const startedAt = new Date().toISOString()
  const autoPull = options.autoPull !== false

  await saveRun(ctx.userId, {
    syncId,
    meetingId: ctx.meetingId,
    generation: Date.now(),
    startedAt,
    status: 'running',
  })

  const summary: SyncSummary = {
    meetingId: ctx.meetingId,
    startedAt,
    finishedAt: startedAt,
    pulled: 0,
    pushed: 0,
    deleted: 0,
    skipped: 0,
    conflicts: 0,
    failed: 0,
  }

  await recoverInterrupted(ctx)

  const baselines = await loadBaselines(ctx.userId, ctx.meetingId)
  const localSnapshot = await buildLocalSnapshot(ctx)
  await enrichWithHashes(localSnapshot.entries, localSnapshot.files, baselines)
  const remotes = await buildRemoteSnapshot(ctx)

  const input: ReconcileInput = {
    meetingId: ctx.meetingId,
    baselines,
    locals: localSnapshot.entries,
    remotes,
    allowPushCreate: true,
    allowPushUpdate: true,
    allowDeleteLocal: false,
  }
  const plan = reconcile(input)

  const remoteById = new Map(remotes.map((item) => [item.remoteId, item]))

  await appendSyncEvent(
    ctx.userId,
    makeEvent(ctx, syncId, 'scan', 'ok', {
      message: `本地 ${localSnapshot.entries.length} 项 / 远端 ${remotes.length} 项`,
    }),
  )

  for (const action of plan.actions) {
    try {
      if (action.kind === 'pull-create' || action.kind === 'pull-update') {
        if (!autoPull) {
          summary.skipped += 1
          continue
        }
        await saveActionRecord(ctx.userId, {
          actionId: newId('act'),
          syncId,
          meetingId: ctx.meetingId,
          relPath: action.relPath,
          kind: action.kind,
          phase: 'in-flight',
          at: new Date().toISOString(),
        })
        await pullEntry(ctx, action, remoteById.get(action.remoteId ?? ''))
        const stat = await statAfterWrite(ctx, action.relPath)
        await writeBaseline(ctx, action, remoteById.get(action.remoteId ?? ''), stat)
        summary.pulled += 1
        await appendSyncEvent(
          ctx.userId,
          makeEvent(ctx, syncId, 'pull', 'ok', {
            relPath: action.relPath,
            remoteId: action.remoteId ?? undefined,
            category: action.category,
          }),
        )
        continue
      }

      if (action.kind === 'adopt') {
        if (action.remoteId) {
          const remote = remoteById.get(action.remoteId)
          await writeBaseline(
            ctx,
            action,
            remote,
            remote
              ? { size: remote.size ?? 0, mtime: Date.now(), hash: null }
              : { size: 0, mtime: Date.now(), hash: null },
          )
        } else {
          await deleteBaselineFor(ctx.userId, ctx.meetingId, action.relPath)
        }
        summary.skipped += 1
        continue
      }
    } catch (caught) {
      const error = toLocalFsError(caught)
      summary.failed += 1
      await appendSyncEvent(
        ctx.userId,
        makeEvent(ctx, syncId, 'error', 'failed', {
          relPath: action.relPath,
          errorCode: error.code,
          message: error.message,
        }),
      )
      // 网络/临时失败进重试队列；权限类失败不重试（等用户恢复授权）
      if (error.code === 'io' || error.code === 'quota') {
        await enqueueRetry(ctx.userId, {
          queueId: newId('que'),
          meetingId: ctx.meetingId,
          relPath: action.relPath,
          kind: action.kind,
          attempts: 1,
          nextAttemptAt: new Date(Date.now() + 30_000).toISOString(),
          lastError: error.message,
          at: new Date().toISOString(),
        })
      }
    }
  }

  summary.conflicts = plan.conflicts.length
  summary.finishedAt = new Date().toISOString()

  for (const conflict of plan.conflicts) {
    await appendSyncEvent(
      ctx.userId,
      makeEvent(ctx, syncId, 'conflict-open', 'conflict', {
        relPath: conflict.relPath,
        remoteId: conflict.remoteId ?? undefined,
        message: conflict.detail,
      }),
    )
  }

  // 同步清单是 IDB 的镜像，失败不影响同步结果
  try {
    const latest = await loadBaselines(ctx.userId, ctx.meetingId)
    await writeManifest(
      ctx.root,
      ctx.meetingRoot,
      buildManifest(ctx.meetingId, ctx.meetingTitle, latest, plan.conflicts),
    )
  } catch {
    /* 忽略 */
  }

  await saveRun(ctx.userId, {
    syncId,
    meetingId: ctx.meetingId,
    generation: Date.now(),
    startedAt,
    finishedAt: summary.finishedAt,
    status: 'done',
  })

  return { summary, plan }
}

/** 启动时清点待重试项：超过 5 次直接丢弃，其余留给下一轮 */
async function recoverInterrupted(ctx: RunSyncContext): Promise<void> {
  const queued = await loadRetryQueue(ctx.userId, ctx.meetingId)
  const now = Date.now()
  for (const op of queued) {
    if (op.attempts >= 5) {
      await dequeueRetry(ctx.userId, op.queueId)
      continue
    }
    if (new Date(op.nextAttemptAt).getTime() > now) {
      continue
    }
    await appendSyncEvent(
      ctx.userId,
      makeEvent(ctx, 'recover', 'recover', 'skipped', {
        relPath: op.relPath,
        message: `待重试 ${op.kind}（第 ${op.attempts} 次）`,
      }),
    )
  }
}

/* ============================================================
 * 确认式动作：用户点击后才执行的回写
 * ============================================================ */

export interface ConfirmedPushInput {
  ctx: RunSyncContext
  action: SyncAction
  file?: File
  text?: string
  expectedUpdatedAt?: string
  expectedVersion?: number
}

/** 用户确认后执行回写；创建类操作用 `client_op_id` 保证幂等 */
export async function executeConfirmedPush(
  input: ConfirmedPushInput,
): Promise<SyncBaseline | null> {
  const { ctx, action } = input
  const clientOpId = newId('cli')

  if (action.kind === 'push-create') {
    if (action.category === 'material' && input.file) {
      const created = await materialsApi.uploadMaterial(ctx.meetingId, {
        file: input.file,
        source: '本地工作区',
        client_op_id: clientOpId,
      })
      return baselineOf(action, created.material_id, created.created_at, null)
    }
    if (action.category === 'audio' && input.file) {
      const created = await audioApi.uploadAudio(ctx.meetingId, input.file, clientOpId)
      return baselineOf(action, created.audio_id, created.updated_at, null)
    }
    if (action.category === 'record') {
      const created = await recordsApi.createRecord(ctx.meetingId, {
        content: input.text ?? '',
        record_type: 'imported',
        client_op_id: clientOpId,
      })
      return baselineOf(action, created.record_id, created.updated_at, null)
    }
    if (action.category === 'action_item') {
      const created = await actionItemsApi.createActionItem(ctx.meetingId, {
        content: input.text ?? '',
        client_op_id: clientOpId,
      })
      return baselineOf(action, created.action_id, created.updated_at, null)
    }
    if (action.category === 'issue') {
      const created = await issuesApi.createIssue(ctx.meetingId, {
        description: input.text ?? '',
        client_op_id: clientOpId,
      })
      return baselineOf(action, created.issue_id, created.updated_at, null)
    }
  }

  if (action.kind === 'push-update' && action.remoteId) {
    if (action.category === 'minutes') {
      const updated = await minutesApi.updateMinutes(action.remoteId, {
        content: input.text ?? '',
        expected_version: input.expectedVersion,
      })
      return baselineOf(action, updated.minutes_id, updated.updated_at, updated.version)
    }
    if (action.category === 'record') {
      const updated = await recordsApi.updateRecord(action.remoteId, {
        content: input.text ?? '',
        expected_updated_at: input.expectedUpdatedAt,
      })
      return baselineOf(action, updated.record_id, updated.updated_at, null)
    }
    if (action.category === 'action_item') {
      const updated = await actionItemsApi.updateActionItem(action.remoteId, {
        content: input.text ?? '',
        expected_updated_at: input.expectedUpdatedAt,
      })
      return baselineOf(action, updated.action_id, updated.updated_at, null)
    }
    if (action.category === 'issue') {
      const updated = await issuesApi.updateIssue(action.remoteId, {
        description: input.text ?? '',
        expected_updated_at: input.expectedUpdatedAt,
      })
      return baselineOf(action, updated.issue_id, updated.updated_at, null)
    }
  }

  return null
}

function baselineOf(
  action: SyncAction,
  remoteId: string,
  remoteUpdatedAt: string,
  remoteVersion: number | null,
): SyncBaseline {
  return {
    relPath: action.relPath,
    category: (action.category ?? 'material') as WorkspaceCategory,
    remoteId,
    localSize: 0,
    localMtime: Date.now(),
    localHash: null,
    remoteUpdatedAt,
    remoteVersion,
    syncedAt: new Date().toISOString(),
  }
}
