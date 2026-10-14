import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import { createAppRouter } from '@/router'
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

describe('router guard', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('redirects unauthenticated users from a protected route to login', async () => {
    const router = createAppRouter()
    await router.push('/meetings')

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/meetings')
  })

  it('redirects authenticated users away from guest-only routes', async () => {
    setToken('token-abc')
    vi.mocked(authApi.fetchCurrentUser).mockResolvedValue(user)
    const router = createAppRouter()

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('meetings')
  })

  it('loads the current user before entering a protected route', async () => {
    setToken('token-abc')
    vi.mocked(authApi.fetchCurrentUser).mockResolvedValue(user)
    const router = createAppRouter()

    await router.push('/meetings')

    expect(router.currentRoute.value.name).toBe('meetings')
    expect(authApi.fetchCurrentUser).toHaveBeenCalledTimes(1)
  })

  it('logs out and returns to login when the session cannot be restored', async () => {
    setToken('expired-token')
    vi.mocked(authApi.fetchCurrentUser).mockRejectedValue(new Error('expired'))
    vi.mocked(authApi.logout).mockResolvedValue(undefined)
    const router = createAppRouter()

    await router.push('/meetings')

    expect(router.currentRoute.value.name).toBe('login')
    expect(getToken()).toBeNull()
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('sends unauthenticated visitors from the root path to login', async () => {
    const router = createAppRouter()
    await router.push('/')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('sends authenticated visitors from the root path to meetings', async () => {
    setToken('token-abc')
    vi.mocked(authApi.fetchCurrentUser).mockResolvedValue(user)
    const router = createAppRouter()

    await router.push('/')

    expect(router.currentRoute.value.name).toBe('meetings')
  })

  it('redirects unknown routes to the landing path', async () => {
    const router = createAppRouter()
    await router.push('/does-not-exist')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('keeps the health page reachable at /home', async () => {
    const router = createAppRouter()
    await router.push('/home')

    expect(router.currentRoute.value.name).toBe('home')
  })
})
