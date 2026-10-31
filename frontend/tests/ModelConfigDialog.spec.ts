import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as settingsApi from '@/api/settings'
import ModelConfigDialog from '@/components/settings/ModelConfigDialog.vue'
import type { ModelConfig } from '@/types/modelConfig'

vi.mock('@/api/settings', () => ({
  getModelConfig: vi.fn(),
  saveModelConfig: vi.fn(),
  savePurposeModels: vi.fn(),
  clearModelConfig: vi.fn(),
}))

const baseConfig: ModelConfig = {
  llm_api_base: '',
  llm_model: '',
  llm_api_key_masked: '',
  llm_source: 'none',
  llm_purpose_models: {},
  embedding_api_base: '',
  embedding_model: '',
  embedding_api_key_masked: '',
  embedding_source: 'none',
  embedding_dim: 1024,
}

function userLlmConfig(): ModelConfig {
  return {
    ...baseConfig,
    llm_api_base: 'https://api.deepseek.com/v1',
    llm_model: 'deepseek-chat',
    llm_api_key_masked: 'sk-***abc',
    llm_source: 'user',
  }
}

function mountDialog() {
  setActivePinia(createPinia())
  return mount(ModelConfigDialog, { props: { open: true } })
}

describe('ModelConfigDialog', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(baseConfig)
  })

  it('lists the provider presets and the custom option', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const options = wrapper.findAll('#model-provider option').map((node) => node.text())
    expect(options).toEqual([
      '请选择提供商',
      'DeepSeek',
      '智谱 GLM',
      '月之暗面 Kimi',
      '阿里通义千问',
      'OpenAI',
      '硅基流动',
      'OpenRouter',
      '自定义（OpenAI 兼容）',
    ])
  })

  it('saves a preset provider with its default model when only the API key is filled', async () => {
    vi.mocked(settingsApi.saveModelConfig).mockResolvedValue(userLlmConfig())
    const wrapper = mountDialog()
    await flushPromises()

    await wrapper.find('#model-provider').setValue('deepseek')
    await wrapper.find('#model-api-key').setValue('sk-test-key')
    await wrapper.find('form, .model-dialog').trigger('submit')
    const saveButton = wrapper.findAll('button').find((node) => node.text() === '保存配置')
    await saveButton?.trigger('click')
    await flushPromises()

    expect(settingsApi.saveModelConfig).toHaveBeenCalledWith({
      llm_api_base: 'https://api.deepseek.com/v1',
      llm_api_key: 'sk-test-key',
      llm_model: 'deepseek-chat',
    })
  })

  it('warns before clearing a user-configured embedding provider', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue({
      ...userLlmConfig(),
      embedding_api_base: 'https://api.example.com/v1',
      embedding_model: 'text-embedding-model',
      embedding_api_key_masked: 'ek-***xyz',
      embedding_source: 'user',
    })
    vi.mocked(settingsApi.saveModelConfig).mockResolvedValue(userLlmConfig())
    const wrapper = mountDialog()
    await flushPromises()

    await wrapper.find('#model-provider').setValue('deepseek')
    await wrapper.find('#model-api-key').setValue('sk-test-key')
    const saveButton = wrapper.findAll('button').find((node) => node.text() === '保存配置')
    await saveButton?.trigger('click')
    await flushPromises()

    // 未直接保存，而是先弹出确认提醒
    expect(settingsApi.saveModelConfig).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('回退服务端默认')
  })
})
