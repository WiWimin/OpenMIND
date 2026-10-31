// 会议模板（内置 + 用户自定义），与后端 schemas/meeting_template.py 对齐
export type TemplateSource = 'builtin' | 'custom'

export interface MeetingTemplate {
  template_id: string
  name: string
  description: string | null
  source: TemplateSource
  file_name: string | null
  created_at: string | null
}

export interface MeetingTemplateDetail extends MeetingTemplate {
  content_text: string
}

export interface UploadTemplatePayload {
  file: File
  name?: string
  description?: string
}
