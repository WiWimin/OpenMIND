import type { RecordMarkerType } from './record'

export type AudioStatus = 'uploaded' | 'processing' | 'transcribed' | 'failed' | 'confirmed'

/** 转写分段：seq 从 1 连续递增，offset_seconds 为录音内相对秒数（与后端 AudioSegment 对齐） */
export interface AudioSegment {
  seq: number
  offset_seconds: number
  text: string
  marker_type?: RecordMarkerType | null
  error?: string | null
}

export interface MeetingAudio {
  audio_id: string
  meeting_id: string
  file_name: string
  type: string
  // 本地工作区同步：文件字节数（后端未返回时为 null）
  file_size?: number | null
  status: AudioStatus
  transcript: string | null
  segments: AudioSegment[] | null
  error: string | null
  record_id: string | null
  created_at: string
  updated_at: string
}

/** 转写流条目：转写分段与会议记录统一后的展示模型 */
export interface TranscriptEntry {
  /** `seg-{audioId}-{seq}` 或 `rec-{recordId}` */
  key: string
  kind: 'segment' | 'record'
  /** 分段序号（record 条目为 null） */
  seq: number | null
  /** 展示用时间标签（mm:ss 或 HH:MM） */
  time: string
  text: string
  /** 分段原始正文（展示可能是占位文案；空值表示无可编辑内容） */
  rawText?: string
  marker: RecordMarkerType | null
  /** record 条目的类型标签（手动记录 / 转写 / 导入） */
  tag?: string
  recordId?: string
  error?: string | null
}
