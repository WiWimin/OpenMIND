import http from '@/api/client'
import type { ApiSuccess } from '@/types/api'
import type { AuthUser, LoginPayload, LoginResult, RegisterPayload } from '@/types/auth'
import { unwrapData } from '@/utils/apiEnvelope'

export async function register(payload: RegisterPayload): Promise<AuthUser> {
  const { data } = await http.post<ApiSuccess<AuthUser> | AuthUser>('/auth/register', payload)
  return unwrapData<AuthUser>(data)
}

export async function login(payload: LoginPayload): Promise<LoginResult> {
  const { data } = await http.post<ApiSuccess<LoginResult> | LoginResult>('/auth/login', payload)
  return unwrapData<LoginResult>(data)
}

export async function logout(): Promise<void> {
  await http.post('/auth/logout')
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const { data } = await http.get<ApiSuccess<AuthUser> | AuthUser>('/auth/me')
  return unwrapData<AuthUser>(data)
}
