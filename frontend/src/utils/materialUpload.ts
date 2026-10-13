import { ALLOWED_MATERIAL_EXTENSIONS, MAX_UPLOAD_MB } from '@/constants/upload'

export function fileExtension(fileName: string): string {
  const index = fileName.lastIndexOf('.')
  return index === -1 ? '' : fileName.slice(index + 1).toLowerCase()
}

export function validateMaterialFile(file: File, maxMb: number = MAX_UPLOAD_MB): string | null {
  const extension = fileExtension(file.name)
  if (!(ALLOWED_MATERIAL_EXTENSIONS as readonly string[]).includes(extension)) {
    return `仅支持 ${ALLOWED_MATERIAL_EXTENSIONS.join(' / ')} 文件`
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `文件不能超过 ${maxMb} MB`
  }
  return null
}
