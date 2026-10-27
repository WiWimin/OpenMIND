import type { ActionItemStatus } from '@/types/actionItem'
import type { AudioStatus } from '@/types/audio'
import type { IssueStatus } from '@/types/issue'
import type { KnowledgeStatus } from '@/types/knowledge'
import type { MaterialProcessingStatus } from '@/types/material'
import type { MeetingStatus } from '@/types/meeting'
import type { MinutesStatus, MinutesTemplate } from '@/types/minutes'
import type { PreparationStatus } from '@/types/preparation'
import type { RecordMarkerType } from '@/types/record'
import type { TaskStatus } from '@/types/task'
import type { StatusTone } from '@/types/ui'

export interface StatusMeta {
  label: string
  tone: StatusTone
}

export const meetingStatusMeta: Record<MeetingStatus, StatusMeta> = {
  scheduled: { label: '已安排', tone: 'info' },
  archived: { label: '已归档', tone: 'neutral' },
}

export const materialStatusMeta: Record<MaterialProcessingStatus, StatusMeta> = {
  uploaded: { label: '已上传', tone: 'neutral' },
  processing: { label: '解析中', tone: 'info' },
  processed: { label: '已解析', tone: 'success' },
  failed: { label: '解析失败', tone: 'danger' },
}

export const knowledgeStatusMeta: Record<KnowledgeStatus, StatusMeta> = {
  uploaded: { label: '已上传', tone: 'neutral' },
  processing: { label: '解析中', tone: 'info' },
  processed: { label: '已索引', tone: 'success' },
  failed: { label: '解析失败', tone: 'danger' },
}

export const audioStatusMeta: Record<AudioStatus, StatusMeta> = {
  uploaded: { label: '已上传', tone: 'neutral' },
  processing: { label: '转写中', tone: 'info' },
  transcribed: { label: '已转写', tone: 'success' },
  failed: { label: '转写失败', tone: 'danger' },
  confirmed: { label: '已保存', tone: 'success' },
}

export const preparationStatusMeta: Record<PreparationStatus, StatusMeta> = {
  generating: { label: '生成中', tone: 'info' },
  draft: { label: '草稿', tone: 'neutral' },
  confirmed: { label: '已确认', tone: 'success' },
  failed: { label: '生成失败', tone: 'danger' },
}

export const minutesStatusMeta: Record<MinutesStatus, StatusMeta> = {
  draft: { label: '草稿', tone: 'neutral' },
  confirmed: { label: '已确认', tone: 'success' },
}

export const minutesTemplateMeta: Record<MinutesTemplate, StatusMeta> = {
  standard: { label: '标准纪要', tone: 'neutral' },
  concise: { label: '简洁记录', tone: 'info' },
  task_list: { label: '任务清单', tone: 'warning' },
}

export const recordMarkerMeta: Record<RecordMarkerType, StatusMeta> = {
  highlight: { label: '重点', tone: 'warning' },
  decision: { label: '决议', tone: 'success' },
  question: { label: '疑问', tone: 'info' },
}

export const actionItemStatusMeta: Record<ActionItemStatus, StatusMeta> = {
  pending_confirmation: { label: '待确认', tone: 'warning' },
  confirmed: { label: '已确认', tone: 'info' },
  converted: { label: '已转任务', tone: 'success' },
  cancelled: { label: '已取消', tone: 'neutral' },
}

export const taskStatusMeta: Record<TaskStatus, StatusMeta> = {
  todo: { label: '待办', tone: 'neutral' },
  in_progress: { label: '进行中', tone: 'info' },
  completed: { label: '已完成', tone: 'success' },
  cancelled: { label: '已取消', tone: 'neutral' },
}

export const issueStatusMeta: Record<IssueStatus, StatusMeta> = {
  open: { label: '待处理', tone: 'warning' },
  resolved: { label: '已解决', tone: 'success' },
  cancelled: { label: '已取消', tone: 'neutral' },
}

export function resolveStatusMeta<T extends string>(
  map: Partial<Record<T, StatusMeta>>,
  status: T,
  fallbackTone: StatusTone = 'neutral',
): StatusMeta {
  return map[status] ?? { label: status, tone: fallbackTone }
}
