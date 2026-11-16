import http from '@/api/client'
import { extractJob, requireResourceId, waitForJob, type JobAccepted } from '@/api/jobs'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, ListData } from '@/types/api'
import type { PageParams } from '@/types/pagination'
import type {
  GeneratePreparationPayload,
  Preparation,
  UpdatePreparationPayload,
} from '@/types/preparation'
import { unwrapData } from '@/utils/apiEnvelope'

async function fetchPreparation(preparationId: string): Promise<Preparation> {
  const { data } = await http.get<ApiSuccess<Preparation> | Preparation>(
    `/preparations/${preparationId}`,
  )
  return unwrapData(data)
}

// 异步任务（api.md 1.9）：202 受理时 resource_id 为 generating 占位稿 id，
// 轮询到终态后回查准备稿详情（占位转 draft），调用方契约不变
export async function generatePreparation(
  meetingId: string,
  payload: GeneratePreparationPayload,
  signal?: AbortSignal,
): Promise<Preparation> {
  const { data } = await http.post<
    ApiSuccess<Preparation | JobAccepted> | Preparation | JobAccepted
  >(
    `/meetings/${meetingId}/prepare`,
    payload,
    { signal, timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  const accepted = unwrapData<Preparation | JobAccepted>(data)
  const job = extractJob(accepted)
  if (!job) {
    return accepted as Preparation
  }
  const finished = await waitForJob(job.job_id, { signal })
  return fetchPreparation(requireResourceId(finished))
}

export async function listPreparations(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<Preparation>> {
  const { data } = await http.get<ApiSuccess<ListData<Preparation>> | ListData<Preparation>>(
    `/meetings/${meetingId}/preparations`,
    { params },
  )
  return unwrapData(data)
}

export async function updatePreparation(
  preparationId: string,
  payload: UpdatePreparationPayload,
): Promise<Preparation> {
  const { data } = await http.patch<ApiSuccess<Preparation> | Preparation>(
    `/preparations/${preparationId}`,
    payload,
  )
  return unwrapData(data)
}

export async function confirmPreparation(preparationId: string): Promise<Preparation> {
  const { data } = await http.post<ApiSuccess<Preparation> | Preparation>(
    `/preparations/${preparationId}/confirm`,
  )
  return unwrapData(data)
}
