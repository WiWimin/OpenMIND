import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as settingsApi from '@/api/settings'
import { useModelConfigStore } from '@/stores/modelConfig'
import type { ModelConfig } from '@/types/modelConfig'

vi.mock('@/api/settings', () => ({
  getModelConfig: vi.fn(),
  saveModelConfig: vi.fn(),
  savePurposeModels: vi.fn(),
  clearModelConfig: vi.fn(),
}))

const config: ModelConfig = {
  llm_api_base: 'https://llm.example.com/v1',
  llm_model: 'custom-model',
  llm_api_key_masked: 'sk-...-key',
  llm_source: 'user',
  llm_purpose_models: {},
  embedding_api_base: 'https://emb.example.com/v1',
  embedding_model: 'text-embedding-1024',
  embedding_api_key_masked: 'sk-...-key',
  embedding_source: 'user',
  embedding_dim: 1024,
}

describe('modelConfig store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('loads the effective config', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(config)

    const store = useModelConfigStore()
    await store.load()

    expect(store.config).toEqual(config)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('saves a config and updates state', async () => {
    const payload = { llm_api_base: 'a', llm_api_key: 'b', llm_model: 'c' }
    vi.mocked(settingsApi.saveModelConfig).mockResolvedValue(config)

    const store = useModelConfigStore()
    await store.save(payload)

    expect(settingsApi.saveModelConfig).toHaveBeenCalledWith(payload)
    expect(store.config).toEqual(config)
    expect(store.saving).toBe(false)
  })

  it('saves purpose models and updates state', async () => {
    const payload = { models: { minutes: 'minutes-model' } }
    const updated = {
      ...config,
      llm_purpose_models: { minutes: 'minutes-model' },
    }
    vi.mocked(settingsApi.savePurposeModels).mockResolvedValue(updated)

    const store = useModelConfigStore()
    await store.savePurposes(payload)

    expect(settingsApi.savePurposeModels).toHaveBeenCalledWith(payload)
    expect(store.config).toEqual(updated)
    expect(store.saving).toBe(false)
  })

  it('clears config then reloads the effective config', async () => {
    vi.mocked(settingsApi.clearModelConfig).mockResolvedValue({ deleted: true })
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue({ ...config, llm_source: 'global' })

    const store = useModelConfigStore()
    await store.clear()

    expect(settingsApi.clearModelConfig).toHaveBeenCalledTimes(1)
    expect(store.config?.llm_source).toBe('global')
  })

  it('records the error when loading fails', async () => {
    vi.mocked(settingsApi.getModelConfig).mockRejectedValue(new Error('boom'))

    const store = useModelConfigStore()
    await expect(store.load()).rejects.toThrow('boom')

    expect(store.error).toBeInstanceOf(Error)
    expect(store.loading).toBe(false)
  })
})
