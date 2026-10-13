const TOKEN_KEY = 'openmind.auth.token'

function getStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

export function getToken(): string | null {
  return getStorage()?.getItem(TOKEN_KEY) ?? null
}

export function setToken(token: string): void {
  getStorage()?.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  getStorage()?.removeItem(TOKEN_KEY)
}
