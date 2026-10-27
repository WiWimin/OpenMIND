export type AudioStatus = 'uploaded' | 'processing' | 'transcribed' | 'failed' | 'confirmed'

export interface MeetingAudio {
  audio_id: string
  meeting_id: string
  file_name: string
  type: string
  status: AudioStatus
  transcript: string | null
  error: string | null
  record_id: string | null
  created_at: string
  updated_at: string
}
