import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import {
  clearModelConfig,
  getModelConfig,
  saveModelConfig,
} from '@/api/settings'
import type { ModelConfigRead } from '@/types/modelConfig'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const put = vi.mocked(http.put)
const del = vi.mocked(http.delete)

const config: ModelConfigRead = {
  llm_api_base: 'https://llm.example.com/v1',
  llm_model: 'custom-model',
  llm_api_key_masked: 'sk-...abcd',
  embedding_api_base: 'https://emb.example.com/v1',
  embedding_model: 'text-embedding-1024',
  embedding_api_key_masked: 'sk-...wxyz',
  embedding_dim: 1024,
}

describe('settings api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('gets the effective model config', async () => {
    get.mockResolvedValue(response({ status: 'success', data: config }))

    await expect(getModelConfig()).resolves.toEqual(config)
    expect(get).toHaveBeenCalledWith('/me/settings/model')
  })

  it('saves model config', async () => {
    put.mockResolvedValue(response(config))

    await expect(saveModelConfig({ llm_model: 'custom-model' })).resolves.toEqual(config)
    expect(put).toHaveBeenCalledWith('/me/settings/model', { llm_model: 'custom-model' })
  })

  it('clears model config', async () => {
    del.mockResolvedValue(response({ status: 'success', data: { deleted: true } }))

    await expect(clearModelConfig()).resolves.toEqual({ deleted: true })
    expect(del).toHaveBeenCalledWith('/me/settings/model')
  })
})
