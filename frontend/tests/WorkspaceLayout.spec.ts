import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import { useAuthStore } from '@/stores/auth'
import type { AuthUser } from '@/types/auth'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

const user: AuthUser = {
  user_id: 'u1',
  name: 'Alice',
  created_at: '2026-10-01T00:00:00+08:00',
}

function mountLayout() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = user
  return {
    auth,
    wrapper: mount(WorkspaceLayout, {
      global: { plugins: [pinia], stubs: { RouterView: true, RouterLink: true } },
    }),
  }
}

describe('WorkspaceLayout', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetAllMocks()
  })

  it('shows the current user name', () => {
    const { wrapper } = mountLayout()
    expect(wrapper.text()).toContain('Alice')
  })

  it('logs out and returns to the login page', async () => {
    vi.mocked(authApi.logout).mockResolvedValue(undefined)
    const { auth, wrapper } = mountLayout()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(authApi.logout).toHaveBeenCalledTimes(1)
    expect(auth.isAuthenticated).toBe(false)
    expect(pushMock).toHaveBeenCalledWith({ name: 'login' })
  })
})
