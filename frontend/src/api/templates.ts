import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess } from '@/types/api'
import type {
  MeetingTemplate,
  MeetingTemplateDetail,
  UploadTemplatePayload,
} from '@/types/template'
import { unwrapData } from '@/utils/apiEnvelope'

const PATH = '/meeting-templates'

export async function listTemplates(): Promise<MeetingTemplate[]> {
  const { data } = await http.get<ApiSuccess<MeetingTemplate[]> | MeetingTemplate[]>(PATH)
  return unwrapData(data)
}

export async function getTemplate(templateId: string): Promise<MeetingTemplateDetail> {
  const { data } = await http.get<
    ApiSuccess<MeetingTemplateDetail> | MeetingTemplateDetail
  >(`${PATH}/${templateId}`)
  return unwrapData(data)
}

export async function uploadTemplate(
  payload: UploadTemplatePayload,
): Promise<MeetingTemplate> {
  const form = new FormData()
  form.append('file', payload.file)
  if (payload.name) {
    form.append('name', payload.name)
  }
  if (payload.description) {
    form.append('description', payload.description)
  }
  const { data } = await http.post<ApiSuccess<MeetingTemplate> | MeetingTemplate>(
    PATH,
    form,
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  return unwrapData(data)
}

export async function deleteTemplate(templateId: string): Promise<{ deleted: boolean }> {
  const { data } = await http.delete<
    ApiSuccess<{ deleted: boolean }> | { deleted: boolean }
  >(`${PATH}/${templateId}`)
  return unwrapData(data)
}
