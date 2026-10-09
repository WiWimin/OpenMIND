import { describe, expect, it } from 'vitest'

import type { ApiError } from '@/types/api'
import { resolveErrorMessage } from '@/utils/errors'

describe('resolveErrorMessage', () => {
  it('uses the message from a normalized ApiError', () => {
    const error: ApiError = {
      status: 'error',
      error_code: 'VALIDATION_ERROR',
      message: '用户名或密码错误',
    }
    expect(resolveErrorMessage(error)).toBe('用户名或密码错误')
  })

  it('falls back to the Error message', () => {
    expect(resolveErrorMessage(new Error('boom'))).toBe('boom')
  })

  it('returns the provided fallback for unknown values', () => {
    expect(resolveErrorMessage('unexpected', '自定义提示')).toBe('自定义提示')
  })
})
