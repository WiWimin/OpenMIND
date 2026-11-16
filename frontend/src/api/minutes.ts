import http from '@/api/client'
import { extractJob, waitForJob, type JobAccepted } from '@/api/jobs'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, ApiError, ListData } from '@/types/api'
import type { GenerateMinutesPayload, Minutes, UpdateMinutesPayload } from '@/types/minutes'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

// 异步任务（api.md 1.9）：202 受理时轮询到终态；纪要在任务结束才创建
// （受理时 resource_id 为 null），成功后取列表最新一条，调用方契约不变
export async function generateMinutes(
  meetingId: string,
  payload: GenerateMinutesPayload,
  signal?: AbortSignal,
): Promise<Minutes> {
  const { data } = await http.post<
    ApiSuccess<Minutes | JobAccepted> | Minutes | JobAccepted
  >(
    `/meetings/${meetingId}/minutes/generate`,
    payload,
    { signal, timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  const accepted = unwrapData<Minutes | JobAccepted>(data)
  const job = extractJob(accepted)
  if (!job) {
    return accepted as Minutes
  }
  await waitForJob(job.job_id, { signal })
  const latest = (await listMinutes(meetingId, { page: 1, page_size: 1 })).items[0]
  if (!latest) {
    throw {
      status: 'error',
      error_code: 'INTERNAL_ERROR',
      message: '纪要生成完成但未找到结果，请刷新后重试',
      retryable: true,
    } satisfies ApiError
  }
  return latest
}

// [提案] 纪要读取/编辑/确认接口（api.md 5.11–5.14），待团队确认
export async function listMinutes(
  meetingId: string,
  params: PageParams = {},
): Promise<ListData<Minutes>> {
  const { data } = await http.get<ApiSuccess<ListData<Minutes>> | ListData<Minutes>>(
    `/meetings/${meetingId}/minutes`,
    { params },
  )
  return unwrapData(data)
}

export async function getMinutes(minutesId: string): Promise<Minutes> {
  const { data } = await http.get<ApiSuccess<Minutes> | Minutes>(`/minutes/${minutesId}`)
  return unwrapData(data)
}

export async function updateMinutes(
  minutesId: string,
  payload: UpdateMinutesPayload,
): Promise<Minutes> {
  const { data } = await http.patch<ApiSuccess<Minutes> | Minutes>(
    `/minutes/${minutesId}`,
    payload,
  )
  return unwrapData(data)
}

export async function confirmMinutes(minutesId: string): Promise<Minutes> {
  const { data } = await http.post<ApiSuccess<Minutes> | Minutes>(`/minutes/${minutesId}/confirm`)
  return unwrapData(data)
}
