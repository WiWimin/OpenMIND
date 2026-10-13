import type { AxiosResponse } from 'axios'

export function response<T>(data: T, status = 200): AxiosResponse<T> {
  return {
    data,
    status,
    statusText: 'OK',
    headers: {},
    config: {},
  } as unknown as AxiosResponse<T>
}
