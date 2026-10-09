import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { AuthUser } from '@/types/auth'
import { getToken, setToken } from '@/utils/authToken'

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

const user: AuthUser = {
  user_id: 'user-1',
  name: 'Alice',
  created_at: '2026-10-01T00:00:00+08:00',
}

describe('auth store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('is not authenticated without a token', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('stores the token and user after login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'token-abc',
      token_type: 'bearer',
      user,
    })
    const auth = useAuthStore()

    const result = await auth.login({ name: 'Alice', password: 'secret123' })

    expect(result).toEqual(user)
    expect(auth.user).toEqual(user)
    expect(auth.isAuthenticated).toBe(true)
    expect(getToken()).toBe('token-abc')
  })

  it('clears local state even when the logout request fails', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'token-abc',
      token_type: 'bearer',
      user,
    })
    vi.mocked(authApi.logout).mockRejectedValue(new Error('network'))
    const auth = useAuthStore()
    await auth.login({ name: 'Alice', password: 'secret123' })

    await auth.logout()

    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
    expect(getToken()).toBeNull()
  })

  it('does not fetch the current user without a token', async () => {
    const auth = useAuthStore()
    expect(await auth.loadCurrentUser()).toBeNull()
    expect(authApi.fetchCurrentUser).not.toHaveBeenCalled()
  })

  it('fetches and caches the current user when only a token exists', async () => {
    setToken('token-restored')
    vi.mocked(authApi.fetchCurrentUser).mockResolvedValue(user)
    const auth = useAuthStore()

    await auth.loadCurrentUser()
    await auth.loadCurrentUser()

    expect(authApi.fetchCurrentUser).toHaveBeenCalledTimes(1)
    expect(auth.user).toEqual(user)
  })

  it('delegates registration to the api and does not log in', async () => {
    vi.mocked(authApi.register).mockResolvedValue(user)
    const auth = useAuthStore()

    const registered = await auth.register({ name: 'Alice', password: 'secret123' })

    expect(registered).toEqual(user)
    expect(auth.isAuthenticated).toBe(false)
  })
})
