export const MAX_UPLOAD_MB = 20

export const ALLOWED_MATERIAL_EXTENSIONS = ['pdf', 'docx', 'txt'] as const
export const ALLOWED_AUDIO_EXTENSIONS = ['mp3', 'wav', 'm4a', 'webm'] as const
/** 已转写好的文稿（用户自行转换的 Word / 纯文本），上传后直接解析导入 */
export const ALLOWED_DOCUMENT_EXTENSIONS = ['docx', 'txt'] as const
/** 录音转写页可上传的全部类型 = 音频 + 文稿 */
export const ALLOWED_ASR_UPLOAD_EXTENSIONS = [
  ...ALLOWED_AUDIO_EXTENSIONS,
  ...ALLOWED_DOCUMENT_EXTENSIONS,
] as const
