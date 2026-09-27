import http from '@/api/client'
import type { ConnectionState, HealthPayload } from '@/types/health'

const HEALTH_TIMEOUT_MS = 5000

export async function checkBackendHealth(): Promise<ConnectionState> {
  try {
    const { data } = await http.get<HealthPayload>('/health/db', {
      timeout: HEALTH_TIMEOUT_MS,
    })
    return data.status === 'ok' && data.database === 'up' ? 'up' : 'down'
  } catch {
    return 'down'
  }
}
