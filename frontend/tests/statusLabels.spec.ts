import { describe, expect, it } from 'vitest'

import {
  actionItemStatusMeta,
  issueStatusMeta,
  materialStatusMeta,
  meetingStatusMeta,
  minutesStatusMeta,
  minutesTemplateMeta,
  preparationStatusMeta,
  recordMarkerMeta,
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

  it('maps minutes templates', () => {
    expect(minutesTemplateMeta.standard.label).toBe('标准纪要')
    expect(minutesTemplateMeta.concise.tone).toBe('info')
    expect(minutesTemplateMeta.task_list.label).toBe('任务清单')
  })

  it('maps task statuses', () => {
    expect(taskStatusMeta.in_progress).toEqual({ label: '进行中', tone: 'info' })
  })

  it('maps record marker types', () => {
    expect(recordMarkerMeta.highlight.tone).toBe('warning')
    expect(recordMarkerMeta.decision.label).toBe('决议')
    expect(recordMarkerMeta.question.tone).toBe('info')
  })

  it('maps meeting statuses', () => {
    expect(meetingStatusMeta.scheduled.tone).toBe('info')
    expect(meetingStatusMeta.archived.label).toBe('已归档')
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
