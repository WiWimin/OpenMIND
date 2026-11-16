import http from '@/api/client'
import type { ApiError, ApiSuccess } from '@/types/api'
import { unwrapData } from '@/utils/apiEnvelope'

/**
 * 异步任务（Job）轮询（api.md 1.9）：`ASYNC_JOBS_ENABLED=true` 时长任务端点
 * 返回 `202 + { job }`，这里统一等待终态并转换为业务层可见的结果/错误。
 * 开关关闭时端点仍返回业务对象，`extractJob` 返回 null 走原同步路径。
 */
export type JobStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export interface AsyncJob {
  job_id: string
  job_type: string
  status: JobStatus
  resource_type: string | null
  resource_id: string | null
  progress: number
  error_code: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

/** 202 受理载荷（`Envelope[JobAccepted]` 解包后的 `data`） */
export interface JobAccepted {
  job: AsyncJob
}

/** 轮询间隔与总超时：超过总超时按 JOB_TIMEOUT 失败（可重试） */
export const JOB_POLL_INTERVAL_MS = 1_000
export const JOB_TIMEOUT_MS = 180_000

/**
 * 从端点响应中提取 job：同步契约（开关关闭）没有 `job` 字段时返回 null。
 * 对象缺少合法 `job_id` 时同样视为非受理载荷（走同步路径）。
 */
export function extractJob(payload: unknown): AsyncJob | null {
  if (typeof payload !== 'object' || payload === null || !('job' in payload)) {
    return null
  }
  const job = (payload as JobAccepted).job
  if (typeof job !== 'object' || job === null || typeof job.job_id !== 'string') {
    return null
  }
  return job
}

function jobFailure(job: AsyncJob): ApiError {
  const code = job.error_code ?? 'INTERNAL_ERROR'
  return {
    status: 'error',
    error_code: code,
    message: job.error_message ?? '任务处理失败，请重试。',
    // 校验/权限类失败重试无意义，其余（解析、模型、超时）均可重试
    retryable: code !== 'VALIDATION_ERROR' && code !== 'PERMISSION_DENIED',
  }
}

function abortError(): Error {
  const error = new Error('已取消本次请求。')
  error.name = 'AbortError'
  return error
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const onAbort = (): void => {
      clearTimeout(timer)
      reject(abortError())
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export interface WaitForJobOptions {
  /** 轮询间隔（毫秒），测试可置 0 */
  intervalMs?: number
  /** 总超时（毫秒），超时抛 JOB_TIMEOUT */
  timeoutMs?: number
  signal?: AbortSignal
}

/**
 * 轮询任务直到终态：`succeeded` 返回任务对象；`failed` 抛统一 ApiError
 * （错误码取 `job.error_code`）；超时抛 `JOB_TIMEOUT`；取消抛 AbortError。
 */
export async function waitForJob(
  jobId: string,
  options: WaitForJobOptions = {},
): Promise<AsyncJob> {
  const intervalMs = options.intervalMs ?? JOB_POLL_INTERVAL_MS
  const timeoutMs = options.timeoutMs ?? JOB_TIMEOUT_MS
  const deadline = Date.now() + timeoutMs
  for (;;) {
    if (options.signal?.aborted) {
      throw abortError()
    }
    const { data } = await http.get<ApiSuccess<AsyncJob> | AsyncJob>(`/jobs/${jobId}`, {
      ...(options.signal ? { signal: options.signal } : {}),
    })
    const job = unwrapData(data)
    if (job.status === 'succeeded') {
      return job
    }
    if (job.status === 'failed') {
      throw jobFailure(job)
    }
    if (Date.now() >= deadline) {
      throw {
        status: 'error',
        error_code: 'JOB_TIMEOUT',
        message: '任务处理超时，请重试',
        retryable: true,
      } satisfies ApiError
    }
    await sleep(intervalMs, options.signal)
  }
}

/** 任务成功后取关联资源 id；受理时即应关联，缺失按服务端异常处理（纪要生成除外） */
export function requireResourceId(job: AsyncJob): string {
  if (!job.resource_id) {
    throw {
      status: 'error',
      error_code: 'INTERNAL_ERROR',
      message: '任务未返回关联资源，请刷新后重试',
      retryable: true,
    } satisfies ApiError
  }
  return job.resource_id
}
