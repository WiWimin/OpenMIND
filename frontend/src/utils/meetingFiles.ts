import type { MeetingRecord } from '@/types/record'
import { formatDateTime } from '@/utils/datetime'

/**
 * 会议文件命名工具：
 * 项目内文件列表与本地文件夹镜像必须使用同一份命名，
 * 保证页面上看到的文件名与磁盘上的一致。
 */

/** 保存后的会议记录 → 虚拟 .md 文件名（修改日期精确到秒，避免同分钟重名） */
export function recordFileName(record: Pick<MeetingRecord, 'record_id' | 'created_at'>): string {
  const time = formatDateTime(record.created_at, { withSeconds: true })
  return `会议记录_${time}.md`
}
