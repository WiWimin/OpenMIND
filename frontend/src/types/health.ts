export type ConnectionState = 'checking' | 'up' | 'down'

export interface HealthPayload {
  status: string
  database: string
}
