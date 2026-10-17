import type { ApiError } from '@/types/api'

const DEFAULT_MESSAGE = '操作失败，请稍后重试。'

const ERROR_CODE_FALLBACKS: Record<string, string> = {
  AUTH_REQUIRED: '登录状态已失效，请重新登录',
  VALIDATION_ERROR: '输入不合法，请检查后重试',
  RESOURCE_NOT_FOUND: '资源不存在或无权访问',
  BUSINESS_RULE_VIOLATION: '该操作不被允许',
  RATE_LIMITED: '操作过于频繁，请稍后再试',
  MODEL_TIMEOUT: '模型响应超时，请稍后重试',
  MODEL_OUTPUT_INVALID: '模型返回异常，请重试',
  MODEL_CONFIG_INVALID: '模型配置校验失败，请检查地址、密钥与模型名称',
  INTERNAL_ERROR: '服务暂时不可用，请稍后重试',
  NETWORK_ERROR: '网络连接失败，请检查网络后重试',
}

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
    return error.message || ERROR_CODE_FALLBACKS[error.error_code] || fallback
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}
