export type MaterialProcessingStatus = 'uploaded' | 'processing' | 'processed' | 'failed'

export interface Material {
  material_id: string
  meeting_id: string
  file_name: string
  type: string
  source: string | null
  processing_status: MaterialProcessingStatus
  parse_error: string | null
  // 本地工作区同步：文件字节数（后端未返回时为 null）
  file_size?: number | null
  created_at: string
}

export interface MaterialUploadPayload {
  file: File
  source?: string
  material_type?: string
  // 幂等键：同键重复提交返回已有实体
  client_op_id?: string | null
}

/** 上传失败展示信息：parse=解析失败（422 FILE_PARSE_FAILED），upload=上传/网络等其他失败 */
export interface MaterialUploadError {
  kind: 'parse' | 'upload'
  message: string
}
