import type { Pagination } from '@/types/pagination'

export interface ApiSuccess<T> {
  status: 'success'
  data: T
}

export interface ApiError {
  status: 'error'
  error_code: string
  message: string
  retryable?: boolean
}

export interface ListData<T> {
  items: T[]
  pagination: Pagination
}
