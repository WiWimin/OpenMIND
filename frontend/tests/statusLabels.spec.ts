import { describe, expect, it } from 'vitest'

import {
  actionItemStatusMeta,
  issueStatusMeta,
  materialStatusMeta,
  minutesStatusMeta,
  preparationStatusMeta,
  resolveStatusMeta,
  taskStatusMeta,
} from '@/utils/statusLabels'

describe('status labels', () => {
  it('maps material processing statuses', () => {
    expect(materialStatusMeta.processed).toEqual({ label: '已解析', tone: 'success' })
    expect(materialStatusMeta.failed.tone).toBe('danger')
  })

  it('maps preparation and minutes statuses', () => {
    expect(preparationStatusMeta.generating.tone).toBe('info')
    expect(minutesStatusMeta.confirmed.label).toBe('已确认')
  })

  it('maps task statuses', () => {
    expect(taskStatusMeta.in_progress).toEqual({ label: '进行中', tone: 'info' })
  })

  it('maps action item and issue statuses', () => {
    expect(actionItemStatusMeta.pending_confirmation.tone).toBe('warning')
    expect(actionItemStatusMeta.converted.label).toBe('已转任务')
    expect(issueStatusMeta.open.tone).toBe('warning')
  })

  it('falls back to the raw status when unknown at runtime', () => {
    expect(resolveStatusMeta(taskStatusMeta, 'unknown' as 'todo')).toEqual({
      label: 'unknown',
      tone: 'neutral',
    })
  })
})
