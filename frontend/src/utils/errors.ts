import type { ApiError } from '@/types/api'

const DEFAULT_MESSAGE = '操作失败，请稍后重试。'

function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error_code' in value &&
    'message' in value &&
    typeof (value as ApiError).message === 'string'
  )
}

export function resolveErrorMessage(error: unknown, fallback: string = DEFAULT_MESSAGE): string {
  if (isApiError(error)) {
    return error.message || fallback
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}
