import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import RegisterView from '@/views/auth/RegisterView.vue'

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
  return mount(RegisterView, {
    global: { plugins: [pinia], stubs: { RouterLink: true } },
  })
}

describe('RegisterView', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetAllMocks()
  })

  it('rejects mismatched passwords without calling the api', async () => {
    const wrapper = mountView()

    await wrapper.get('#register-name').setValue('Alice')
    await wrapper.get('#register-password').setValue('secret123')
    await wrapper.get('#register-confirm').setValue('different')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('两次输入的密码不一致')
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('enforces a minimum password length', async () => {
    const wrapper = mountView()

    await wrapper.get('#register-name').setValue('Alice')
    await wrapper.get('#register-password').setValue('123')
    await wrapper.get('#register-confirm').setValue('123')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('密码至少需要 6 位')
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('registers and routes to the login page on success', async () => {
    vi.mocked(authApi.register).mockResolvedValue({
      user_id: 'u1',
      name: 'Alice',
      created_at: '2026-10-01T00:00:00+08:00',
    })
    const wrapper = mountView()

    await wrapper.get('#register-name').setValue('Alice')
    await wrapper.get('#register-password').setValue('secret123')
    await wrapper.get('#register-confirm').setValue('secret123')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(authApi.register).toHaveBeenCalledWith({ name: 'Alice', password: 'secret123' })
    expect(pushMock).toHaveBeenCalledWith({ name: 'login', query: { registered: '1' } })
  })
})
