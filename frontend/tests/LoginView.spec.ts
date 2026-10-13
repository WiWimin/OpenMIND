import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import type { ApiError } from '@/types/api'
import LoginView from '@/views/auth/LoginView.vue'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(LoginView, {
    global: { plugins: [pinia], stubs: { RouterLink: true } },
  })
}

describe('LoginView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetAllMocks()
  })

  it('blocks submission and shows errors when fields are empty', async () => {
    const wrapper = mountView()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入用户名')
    expect(wrapper.text()).toContain('请输入密码')
    expect(authApi.login).not.toHaveBeenCalled()
  })

  it('logs in and redirects to the workspace on success', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'token-abc',
      token_type: 'bearer',
      user: { user_id: 'u1', name: 'Alice', created_at: '2026-10-01T00:00:00+08:00' },
    })
    const wrapper = mountView()

    await wrapper.get('#login-name').setValue('  Alice  ')
    await wrapper.get('#login-password').setValue('secret123')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(authApi.login).toHaveBeenCalledWith({ name: 'Alice', password: 'secret123' })
    expect(pushMock).toHaveBeenCalledWith({ name: 'workspace' })
  })

  it('surfaces a normalized error message when login fails', async () => {
    const failure: ApiError = {
      status: 'error',
      error_code: 'AUTH_REQUIRED',
      message: '用户名或密码错误',
    }
    vi.mocked(authApi.login).mockRejectedValue(failure)
    const wrapper = mountView()

    await wrapper.get('#login-name').setValue('Alice')
    await wrapper.get('#login-password').setValue('wrong')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('用户名或密码错误')
    expect(pushMock).not.toHaveBeenCalled()
  })
})
