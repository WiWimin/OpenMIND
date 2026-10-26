import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { clearMemory, getMemory, saveMemory } from '@/api/memory'
import type { UserMemory } from '@/types/memory'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const put = vi.mocked(http.put)
const del = vi.mocked(http.delete)

const memory: UserMemory = {
  role: '产品经理',
  work_scenarios: 'B2B SaaS',
  communication_style: '结论先行',
  preferred_minutes_template: 'concise',
  updated_at: '2026-10-01T09:00:00+08:00',
}

describe('memory api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('gets memory', async () => {
    get.mockResolvedValue(response(memory))

    await expect(getMemory()).resolves.toEqual(memory)
    expect(get).toHaveBeenCalledWith('/me/memory')
  })

  it('saves memory', async () => {
    const payload = { role: '产品经理', preferred_minutes_template: 'concise' as const }
    put.mockResolvedValue(response(memory))

    await expect(saveMemory(payload)).resolves.toEqual(memory)
    expect(put).toHaveBeenCalledWith('/me/memory', payload)
  })

  it('clears memory', async () => {
    del.mockResolvedValue(response({ deleted: true }))

    await expect(clearMemory()).resolves.toEqual({ deleted: true })
    expect(del).toHaveBeenCalledWith('/me/memory')
  })
})
