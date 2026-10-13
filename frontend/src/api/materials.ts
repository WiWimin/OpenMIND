import http from '@/api/client'
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

// multipart 上传；Content-Type 由浏览器附带 boundary，联调时需实测
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
  const { data } = await http.post<ApiSuccess<Material> | Material>(
    `/meetings/${meetingId}/materials`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return unwrapData(data)
}

export async function getMaterial(materialId: string): Promise<Material> {
  const { data } = await http.get<ApiSuccess<Material> | Material>(`/materials/${materialId}`)
  return unwrapData(data)
}

export async function deleteMaterial(materialId: string): Promise<DeletedResult<'material_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'material_id'>> | DeletedResult<'material_id'>
  >(`/materials/${materialId}`)
  return unwrapData(data)
}
