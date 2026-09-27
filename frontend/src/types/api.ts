export interface ApiError {
  status: 'error'
  error_code: string
  message: string
  retryable?: boolean
}
