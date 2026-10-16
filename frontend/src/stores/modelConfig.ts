import { ref } from 'vue'
import { defineStore } from 'pinia'

import * as settingsApi from '@/api/settings'
import type { ModelConfig, ModelConfigPayload } from '@/types/modelConfig'

export const useModelConfigStore = defineStore('modelConfig', () => {
  const config = ref<ModelConfig | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<unknown>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      config.value = await settingsApi.getModelConfig()
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function save(payload: ModelConfigPayload): Promise<ModelConfig> {
    saving.value = true
    error.value = null
    try {
      const updated = await settingsApi.saveModelConfig(payload)
      config.value = updated
      return updated
    } catch (err) {
      error.value = err
      throw err
    } finally {
      saving.value = false
    }
  }

  async function clear(): Promise<void> {
    saving.value = true
    error.value = null
    try {
      await settingsApi.clearModelConfig()
      config.value = await settingsApi.getModelConfig()
    } catch (err) {
      error.value = err
      throw err
    } finally {
      saving.value = false
    }
  }

  return { config, loading, saving, error, load, save, clear }
})
