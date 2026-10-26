import { ALLOWED_AUDIO_EXTENSIONS, MAX_UPLOAD_MB } from '@/constants/upload'
import { fileExtension } from '@/utils/materialUpload'

export function validateAudioFile(file: File, maxMb: number = MAX_UPLOAD_MB): string | null {
  const extension = fileExtension(file.name)
  if (!(ALLOWED_AUDIO_EXTENSIONS as readonly string[]).includes(extension)) {
    return `仅支持 ${ALLOWED_AUDIO_EXTENSIONS.join(' / ')} 音频`
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `文件不能超过 ${maxMb} MB`
  }
  return null
}
