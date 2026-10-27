// 统一识别被 AbortController 中断的请求（axios 抛出 CanceledError）
export function isRequestCancelled(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }
  const value = error as { name?: string; code?: string }
  return (
    value.name === 'CanceledError' ||
    value.name === 'AbortError' ||
    value.code === 'ERR_CANCELED'
  )
}
