// 会议模板（内置 + 用户自定义），与后端 schemas/meeting_template.py 对齐
export type TemplateSource = 'builtin' | 'custom'
export type TemplateCategory = '会前' | '会后' | '通用'

export const TEMPLATE_CATEGORIES: TemplateCategory[] = ['会前', '会后', '通用']

export interface MeetingTemplate {
  template_id: string
  name: string
  description: string | null
  category: TemplateCategory | null
  source: TemplateSource
  file_name: string | null
  created_at: string | null
  /** 内容预览（前 60 字符），供卡片缩略图渲染 */
  content_preview: string
}

export interface MeetingTemplateDetail extends MeetingTemplate {
  content_text: string
}

export interface UploadTemplatePayload {
  file: File
  name?: string
  description?: string
  category?: string
}

export interface TemplateTextPayload {
  name: string
  description?: string
  category?: string
  content_text: string
}

export interface TemplateGeneratePayload {
  description: string
}

export interface TemplateGenerateDraft {
  name: string
  description: string | null
  category: TemplateCategory | null
  content_text: string
}
