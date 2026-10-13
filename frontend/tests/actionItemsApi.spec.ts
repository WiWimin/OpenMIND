import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import {
  confirmActionItem,
  convertActionItemToTask,
  deleteActionItem,
  extractActionItems,
  getActionItem,
  listActionItems,
  updateActionItem,
} from '@/api/actionItems'
import type { ActionItem } from '@/types/actionItem'
import type { PersonalTask } from '@/types/task'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const patch = vi.mocked(http.patch)
const del = vi.mocked(http.delete)

const actionItem: ActionItem = {
  action_id: 'act_1',
  meeting_id: 'mtg_1',
  content: '完成接口联调',
  assignee: '张三',
  due_date: '2026-10-05',
  status: 'confirmed',
  source: { record_id: 'rec_1', excerpt: '张三负责完成联调' },
  created_at: '2026-10-01T10:05:00+08:00',
  updated_at: '2026-10-01T10:05:00+08:00',
}

const task: PersonalTask = {
  task_id: 'tsk_1',
  user_id: 'usr_1',
  meeting_id: 'mtg_1',
  action_id: 'act_1',
  title: '完成接口联调',
  status: 'todo',
  due_date: '2026-10-05',
  created_at: '2026-10-01T10:10:00+08:00',
  updated_at: '2026-10-01T10:10:00+08:00',
}

describe('action items api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('extracts action items from an items envelope', async () => {
    post.mockResolvedValue(response({ status: 'success', data: { items: [actionItem] } }))

    await expect(extractActionItems('mtg_1', { record_ids: ['rec_1'] })).resolves.toEqual([
      actionItem,
    ])
    expect(post).toHaveBeenCalledWith('/meetings/mtg_1/action-items/extract', {
      record_ids: ['rec_1'],
    })
  })

  it('lists action items from a bare array', async () => {
    get.mockResolvedValue(response([actionItem]))

    await expect(listActionItems('mtg_1')).resolves.toEqual([actionItem])
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/action-items')
  })

  it('gets a single action item', async () => {
    get.mockResolvedValue(response(actionItem))

    await expect(getActionItem('act_1')).resolves.toEqual(actionItem)
    expect(get).toHaveBeenCalledWith('/action-items/act_1')
  })

  it('updates an action item', async () => {
    patch.mockResolvedValue(response(actionItem))

    await expect(updateActionItem('act_1', { assignee: '李四' })).resolves.toEqual(actionItem)
    expect(patch).toHaveBeenCalledWith('/action-items/act_1', { assignee: '李四' })
  })

  it('deletes an action item', async () => {
    const deleted = { deleted: true as const, action_id: 'act_1' }
    del.mockResolvedValue(response({ status: 'success', data: deleted }))

    await expect(deleteActionItem('act_1')).resolves.toEqual(deleted)
    expect(del).toHaveBeenCalledWith('/action-items/act_1')
  })

  it('confirms an action item', async () => {
    post.mockResolvedValue(response(actionItem))

    await expect(confirmActionItem('act_1')).resolves.toEqual(actionItem)
    expect(post).toHaveBeenCalledWith('/action-items/act_1/confirm')
  })

  it('converts an action item to a task', async () => {
    post.mockResolvedValue(response(task))

    await expect(
      convertActionItemToTask('act_1', { title: '完成接口联调' }),
    ).resolves.toEqual(task)
    expect(post).toHaveBeenCalledWith('/action-items/act_1/convert-to-task', {
      title: '完成接口联调',
    })
  })
})
