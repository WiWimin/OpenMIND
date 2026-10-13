import { beforeEach, describe, expect, it } from 'vitest'

import { clearToken, getToken, setToken } from '@/utils/authToken'

describe('authToken', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('returns null when no token is stored', () => {
    expect(getToken()).toBeNull()
  })

  it('stores and reads back a token', () => {
    setToken('token-123')
    expect(getToken()).toBe('token-123')
  })

  it('clears a stored token', () => {
    setToken('token-123')
    clearToken()
    expect(getToken()).toBeNull()
  })
})
