import axios, { type AxiosError, type AxiosInstance } from 'axios'

import type { ApiError } from '@/types/api'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const http: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const payload = error.response?.data
    if (payload && typeof payload === 'object' && 'error_code' in payload) {
      return Promise.reject(payload)
    }
    return Promise.reject({
      status: 'error',
      error_code: 'NETWORK_ERROR',
      message: error.message,
      retryable: true,
    } satisfies ApiError)
  },
)

export default http
