export interface AuthUser {
  user_id: string
  name: string
  created_at: string
}

export interface LoginPayload {
  name: string
  password: string
}

export interface RegisterPayload {
  name: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: AuthUser
}
