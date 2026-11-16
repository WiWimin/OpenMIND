import { describe, expect, it } from 'vitest'

import { categorize, reconcile } from '@/services/localSync/reconcile'
import type { LocalEntry, RemoteEntry, SyncBaseline } from '@/types/localWorkspace'

const MEETING = 'mtg_1'

function local(overrides: Partial<LocalEntry> & { relPath: string }): LocalEntry {
  return {
    name: overrides.relPath.split('/').pop() ?? overrides.relPath,
    ext: (overrides.relPath.split('.').pop() ?? '').toLowerCase(),
    size: 100,
    lastModified: 1_700_000_000_000,
    hash: 'sha256:local',
    ...overrides,
  }
}

function remote(overrides: Partial<RemoteEntry> & { remoteId: string }): RemoteEntry {
  return {
    category: 'material',
    name: '资料.pdf',
    updatedAt: '2026-11-11T10:00:00+08:00',
    version: 1,
    size: 100,
    ...overrides,
  }
}

function baseline(
  overrides: Partial<SyncBaseline> & { relPath: string; remoteId: string },
): SyncBaseline {
  return {
    category: 'material',
    localSize: 100,
    localMtime: 1_700_000_000_000,
    localHash: 'sha256:local',
    remoteUpdatedAt: '2026-11-11T10:00:00+08:00',
    remoteVersion: 1,
    syncedAt: '2026-11-11T10:00:00+08:00',
    ...overrides,
  }
}

function run(input: Parameters<typeof reconcile>[0]) {
  return reconcile(input)
}

describe('categorize', () => {
  it('按路径与扩展名分类', () => {
    expect(categorize('资料/方案.pdf')).toBe('material')
    expect(categorize('会议纪要_周会.md')).toBe('minutes')
    expect(categorize('记录/会议记录_20260101-1000_rec_1.md')).toBe('record')
    expect(categorize('行动项/行动项_act_1.md')).toBe('action_item')
    expect(categorize('未解决问题/问题_iss_1.md')).toBe('issue')
    expect(categorize('音频/录音.mp3')).toBe('audio')
    expect(categorize('会议信息.json')).toBe('derived')
    expect(categorize('周会-会议纪要.docx')).toBe('derived')
    expect(categorize('行动项汇总.md')).toBe('derived')
  })
})

describe('reconcile：无基线', () => {
  it('远端新增 → 直接拉取', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [],
      locals: [],
      remotes: [remote({ remoteId: 'mat_1', name: '资料.pdf' })],
    })
    expect(plan.actions).toHaveLength(1)
    expect(plan.actions[0]).toMatchObject({ kind: 'pull-create', relPath: '资料.pdf' })
    expect(plan.conflicts).toHaveLength(0)
  })

  it('本地新增 → 待确认导入，不自动上传', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [],
      locals: [local({ relPath: '新资料.pdf' })],
      remotes: [],
    })
    expect(plan.prompts).toHaveLength(1)
    expect(plan.prompts[0]).toMatchObject({ kind: 'push-create', relPath: '新资料.pdf' })
    expect(plan.actions).toHaveLength(0)
  })

  it('派生文件不参与回写', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [],
      locals: [local({ relPath: '会议信息.json' })],
      remotes: [],
    })
    expect(plan.prompts).toHaveLength(0)
    expect(plan.actions).toHaveLength(0)
  })

  it('同名同内容 → 建立基线，不重复导入', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [],
      locals: [local({ relPath: '纪要/会议纪要_周会.md', hash: 'sha256:remote' })],
      remotes: [
        remote({
          remoteId: 'min_1',
          category: 'minutes',
          name: '纪要/会议纪要_周会.md',
          content: '正文',
          contentHash: 'sha256:remote',
        }),
      ],
    })
    expect(plan.actions).toHaveLength(1)
    expect(plan.actions[0]).toMatchObject({ kind: 'adopt' })
    expect(plan.conflicts).toHaveLength(0)
  })

  it('同名不同内容 → 冲突，不覆盖任何一侧', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [],
      locals: [local({ relPath: '资料/方案.pdf', hash: 'sha256:a' })],
      remotes: [remote({ remoteId: 'mat_1', name: '资料/方案.pdf', contentHash: 'sha256:b' })],
    })
    expect(plan.conflicts).toHaveLength(1)
    expect(plan.conflicts[0]).toMatchObject({ kind: 'same-name' })
    expect(plan.actions).toHaveLength(0)
    expect(plan.prompts).toHaveLength(0)
  })

  it('关闭 push-create 时本地新增只计为跳过', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [],
      locals: [local({ relPath: '新资料.pdf' })],
      remotes: [],
      allowPushCreate: false,
    })
    expect(plan.prompts).toHaveLength(0)
    expect(plan.noop).toBe(1)
  })
})

describe('reconcile：有基线', () => {
  const base = baseline({
    relPath: '纪要/会议纪要_周会.md',
    remoteId: 'min_1',
    category: 'minutes',
  })
  const unchangedLocal = local({ relPath: '纪要/会议纪要_周会.md' })
  const unchangedRemote = remote({
    remoteId: 'min_1',
    category: 'minutes',
    name: '纪要/会议纪要_周会.md',
  })

  it('两端都没变 → 无动作', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [unchangedLocal],
      remotes: [unchangedRemote],
    })
    expect(plan.actions).toHaveLength(0)
    expect(plan.prompts).toHaveLength(0)
    expect(plan.conflicts).toHaveLength(0)
    expect(plan.noop).toBe(1)
  })

  it('仅本地修改 → 待确认回写，不自动覆盖远端', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [{ ...unchangedLocal, hash: 'sha256:changed', size: 200 }],
      remotes: [unchangedRemote],
    })
    expect(plan.prompts).toHaveLength(1)
    expect(plan.prompts[0]).toMatchObject({ kind: 'push-update' })
    expect(plan.actions).toHaveLength(0)
  })

  it('仅远端修改 → 安全拉取', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [unchangedLocal],
      remotes: [{ ...unchangedRemote, updatedAt: '2026-11-12T10:00:00+08:00', version: 2 }],
    })
    expect(plan.actions).toHaveLength(1)
    expect(plan.actions[0]).toMatchObject({ kind: 'pull-update' })
    expect(plan.conflicts).toHaveLength(0)
  })

  it('双端同时修改 → 冲突，不覆盖', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [{ ...unchangedLocal, hash: 'sha256:changed', size: 200 }],
      remotes: [{ ...unchangedRemote, updatedAt: '2026-11-12T10:00:00+08:00', version: 2 }],
    })
    expect(plan.conflicts).toHaveLength(1)
    expect(plan.conflicts[0]).toMatchObject({ kind: 'both-modified' })
    expect(plan.actions).toHaveLength(0)
    expect(plan.prompts).toHaveLength(0)
  })

  it('仅 touch（size/mtime 变、hash 未变）→ 视为未修改', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [{ ...unchangedLocal, lastModified: 1_800_000_000_000 }],
      remotes: [unchangedRemote],
    })
    expect(plan.actions).toHaveLength(0)
    expect(plan.prompts).toHaveLength(0)
    expect(plan.noop).toBe(1)
  })

  it('本地删除、远端未改 → 待确认删除服务端，不自动传播', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [],
      remotes: [unchangedRemote],
    })
    expect(plan.prompts).toHaveLength(1)
    expect(plan.prompts[0]).toMatchObject({ kind: 'delete-remote' })
    expect(plan.actions).toHaveLength(0)
  })

  it('本地删除、远端已改 → 冲突', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [],
      remotes: [{ ...unchangedRemote, updatedAt: '2026-11-12T10:00:00+08:00' }],
    })
    expect(plan.conflicts).toHaveLength(1)
    expect(plan.conflicts[0]).toMatchObject({ kind: 'delete-vs-modify' })
    expect(plan.prompts).toHaveLength(0)
  })

  it('本地删除但意图是仅本地移除 → 不再回拉，也不删远端', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [
        { ...base, deleteIntent: 'local-only', localDeletedAt: '2026-11-11T11:00:00+08:00' },
      ],
      locals: [],
      remotes: [unchangedRemote],
    })
    expect(plan.actions).toHaveLength(0)
    expect(plan.prompts).toHaveLength(0)
    expect(plan.noop).toBe(1)
  })

  it('远端删除、本地未改 → 保留本地副本，不自动删除', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [unchangedLocal],
      remotes: [],
    })
    expect(plan.prompts).toHaveLength(1)
    expect(plan.prompts[0]).toMatchObject({ kind: 'adopt' })
    expect(plan.actions).toHaveLength(0)
  })

  it('远端删除、本地已改 → 冲突', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [{ ...unchangedLocal, hash: 'sha256:changed', size: 200 }],
      remotes: [],
    })
    expect(plan.conflicts).toHaveLength(1)
    expect(plan.conflicts[0]).toMatchObject({ kind: 'delete-vs-modify' })
  })

  it('两端都删除 → 清理基线', () => {
    const plan = run({
      meetingId: MEETING,
      baselines: [base],
      locals: [],
      remotes: [],
    })
    expect(plan.actions).toHaveLength(1)
    expect(plan.actions[0]).toMatchObject({ kind: 'adopt' })
  })

  it('派生文件被本地修改 → 只提示，不回写', () => {
    const derived = baseline({
      relPath: '会议信息.json',
      remoteId: 'meta',
      category: 'derived',
    })
    const plan = run({
      meetingId: MEETING,
      baselines: [derived],
      locals: [local({ relPath: '会议信息.json', hash: 'sha256:x', size: 300 })],
      remotes: [
        remote({
          remoteId: 'meta',
          category: 'derived',
          name: '会议信息.json',
          updatedAt: '2026-11-11T10:00:00+08:00',
          version: 1,
        }),
      ],
    })
    expect(plan.prompts).toHaveLength(1)
    expect(plan.prompts[0]).toMatchObject({ kind: 'adopt' })
    expect(plan.actions).toHaveLength(0)
    expect(plan.conflicts).toHaveLength(0)
  })
})

describe('reconcile：幂等', () => {
  it('同一输入重复对账结果一致', () => {
    const input = {
      meetingId: MEETING,
      baselines: [baseline({ relPath: '资料/方案.pdf', remoteId: 'mat_1' })],
      locals: [local({ relPath: '资料/方案.pdf', hash: 'sha256:changed', size: 200 })],
      remotes: [
        remote({
          remoteId: 'mat_1',
          name: '资料/方案.pdf',
          updatedAt: '2026-11-12T10:00:00+08:00',
        }),
      ],
    }
    expect(run(input)).toEqual(run(input))
  })
})
