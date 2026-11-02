import { ALLOWED_AUDIO_EXTENSIONS, MAX_UPLOAD_MB } from '@/constants/upload'
import { validateFile } from '@/utils/materialUpload'

export function validateAudioFile(file: File, maxMb: number = MAX_UPLOAD_MB): string | null {
  return validateFile(file, ALLOWED_AUDIO_EXTENSIONS, '音频', maxMb)
}
