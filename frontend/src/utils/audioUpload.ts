import { ALLOWED_ASR_UPLOAD_EXTENSIONS, MAX_UPLOAD_MB } from '@/constants/upload'
import { validateFile } from '@/utils/materialUpload'

/** 录音转写页上传校验：音频与已转写文稿（docx/txt）均可，统一大小限制。 */
export function validateAudioFile(file: File, maxMb: number = MAX_UPLOAD_MB): string | null {
  return validateFile(file, ALLOWED_ASR_UPLOAD_EXTENSIONS, '音频或文稿', maxMb)
}

/** 是否为已转写好的文稿（docx/txt），上传后跳过 ASR 直接解析导入。 */
export function isDocumentUpload(fileName: string): boolean {
  return /\.(docx|txt)$/i.test(fileName)
}
