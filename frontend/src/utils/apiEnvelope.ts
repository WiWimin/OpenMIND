import type { ApiSuccess } from '@/types/api'

function isApiSuccess<T>(value: unknown): value is ApiSuccess<T> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'status' in value &&
    (value as { status?: unknown }).status === 'success' &&
    'data' in value
  )
}

export function unwrapData<T>(payload: ApiSuccess<T> | T): T {
  return isApiSuccess<T>(payload) ? payload.data : (payload as T)
}
