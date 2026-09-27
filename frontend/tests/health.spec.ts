import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosResponse } from 'axios'

import http from '@/api/client'
import { checkBackendHealth } from '@/api/health'
import type { HealthPayload } from '@/types/health'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

const mockedGet = vi.mocked(http.get)

function response(data: HealthPayload): AxiosResponse<HealthPayload> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {},
  } as unknown as AxiosResponse<HealthPayload>
}

describe('checkBackendHealth', () => {
  beforeEach(() => {
    mockedGet.mockReset()
  })

  it('requests the backend and database health endpoint with a timeout', async () => {
    mockedGet.mockResolvedValue(response({ status: 'ok', database: 'up' }))

    await checkBackendHealth()

    expect(mockedGet).toHaveBeenCalledWith('/health/db', { timeout: 5000 })
  })

  it('reports up when the backend and the database are both healthy', async () => {
    mockedGet.mockResolvedValue(response({ status: 'ok', database: 'up' }))

    await expect(checkBackendHealth()).resolves.toBe('up')
  })

  it('reports down when the database is unavailable', async () => {
    mockedGet.mockResolvedValue(response({ status: 'error', database: 'down' }))

    await expect(checkBackendHealth()).resolves.toBe('down')
  })

  it('reports down when the request fails', async () => {
    mockedGet.mockRejectedValue(new Error('Network Error'))

    await expect(checkBackendHealth()).resolves.toBe('down')
  })

  it('reports down when the request times out', async () => {
    mockedGet.mockRejectedValue(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))

    await expect(checkBackendHealth()).resolves.toBe('down')
  })
})
