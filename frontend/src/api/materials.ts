import http from '@/api/client'
import { extractJob, requireResourceId, waitForJob, type JobAccepted } from '@/api/jobs'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type { Material, MaterialUploadPayload } from '@/types/material'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

// [提案] 材料列表接口（api.md 4.3），待团队确认后转正式
export async function listMaterials(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<Material>> {
  const { data } = await http.get<ApiSuccess<ListData<Material>> | ListData<Material>>(
    `/meetings/${meetingId}/materials`,
    { params },
  )
  return unwrapData(data)
}

async function fetchMaterial(materialId: string): Promise<Material> {
  const { data } = await http.get<ApiSuccess<Material> | Material>(`/materials/${materialId}`)
  return unwrapData(data)
}

// multipart 上传；Content-Type 由浏览器附带 boundary，联调时需实测
// 异步任务（api.md 1.9）：202 受理时轮询到终态后回查材料详情，调用方契约不变
export async function uploadMaterial(
  meetingId: string,
  payload: MaterialUploadPayload,
): Promise<Material> {
  const form = new FormData()
  form.append('file', payload.file)
  if (payload.source) {
    form.append('source', payload.source)
  }
  if (payload.material_type) {
    form.append('material_type', payload.material_type)
  }
  const { data } = await http.post<
    ApiSuccess<Material | JobAccepted> | Material | JobAccepted
  >(
    `/meetings/${meetingId}/materials`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: LONG_REQUEST_TIMEOUT_MS,
    },
  )
  const accepted = unwrapData<Material | JobAccepted>(data)
  const job = extractJob(accepted)
  if (!job) {
    return accepted as Material
  }
  const finished = await waitForJob(job.job_id)
  return fetchMaterial(requireResourceId(finished))
}

export async function deleteMaterial(materialId: string): Promise<DeletedResult<'material_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'material_id'>> | DeletedResult<'material_id'>
  >(`/materials/${materialId}`)
  return unwrapData(data)
}
