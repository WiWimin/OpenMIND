import { ALLOWED_MATERIAL_EXTENSIONS, MAX_UPLOAD_MB } from '@/constants/upload'

export function fileExtension(fileName: string): string {
  const index = fileName.lastIndexOf('.')
  return index === -1 ? '' : fileName.slice(index + 1).toLowerCase()
}

export function isAllowedExtension(fileName: string, extensions: readonly string[]): boolean {
  return (extensions as readonly string[]).includes(fileExtension(fileName))
}

/** 通用的文件类型 + 大小校验；返回错误文案或 null。 */
export function validateFile(
  file: File,
  extensions: readonly string[],
  label: string,
  maxMb: number,
): string | null {
  if (!isAllowedExtension(file.name, extensions)) {
    return `仅支持 ${extensions.join(' / ')} ${label}`
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `文件不能超过 ${maxMb} MB`
  }
  return null
}

export function validateMaterialFile(file: File, maxMb: number = MAX_UPLOAD_MB): string | null {
  return validateFile(file, ALLOWED_MATERIAL_EXTENSIONS, '文件', maxMb)
}
