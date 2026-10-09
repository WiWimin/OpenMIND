import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import type { AuthUser, LoginPayload, RegisterPayload } from '@/types/auth'
import { clearToken, getToken, setToken } from '@/utils/authToken'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => Boolean(token.value))

  function reset(): void {
    token.value = null
    user.value = null
    clearToken()
  }

  async function login(payload: LoginPayload): Promise<AuthUser> {
    const result = await authApi.login(payload)
    token.value = result.access_token
    user.value = result.user
    setToken(result.access_token)
    return result.user
  }

  async function register(payload: RegisterPayload): Promise<AuthUser> {
    return authApi.register(payload)
  }

  async function loadCurrentUser(): Promise<AuthUser | null> {
    if (!token.value) {
      return null
    }
    if (user.value) {
      return user.value
    }
    user.value = await authApi.fetchCurrentUser()
    return user.value
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } catch {
      // 退出接口失败不应阻塞本地登出
    }
    reset()
  }

  return { token, user, isAuthenticated, login, register, loadCurrentUser, logout }
})
