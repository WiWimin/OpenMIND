import type { MinutesTemplate } from '@/types/minutes'

export interface UserMemory {
  role: string
  work_scenarios: string
  communication_style: string
  preferred_minutes_template: MinutesTemplate | null
  updated_at: string | null
}

export interface UserMemoryPayload {
  role?: string
  work_scenarios?: string
  communication_style?: string
  preferred_minutes_template?: MinutesTemplate | null
}
