import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import { useAuthStore } from '@/stores/auth'
import type { AuthUser } from '@/types/auth'

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
    currentRoute: { value: { name: 'dashboard' } },
  }),
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

  it('lists nav feature titles in the footer sitemap', () => {
    const { wrapper } = mountLayout()
    const footer = wrapper.get('.workspace__footer-cols')

    expect(footer.text()).toContain('仪表盘')
    expect(footer.text()).toContain('我的会议')
    expect(footer.text()).toContain('我的任务')
    expect(footer.text()).toContain('待办任务')
    expect(footer.text()).toContain('进行中')
    expect(footer.text()).toContain('已完成')
  })

  it('jumps to page sections and task filters from the footer', async () => {
    const { wrapper } = mountLayout()
    const links = wrapper.findAll('.workspace__footer-link')

    await links.find((item) => item.text() === '我的会议')?.trigger('click')
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#section-meetings' })

    await links.find((item) => item.text() === '待办任务')?.trigger('click')
    expect(pushMock).toHaveBeenCalledWith({ path: '/tasks', query: { status: 'todo' } })
  })
})
