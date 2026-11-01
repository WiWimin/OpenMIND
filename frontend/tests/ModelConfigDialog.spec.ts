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

async function fillPresetForm(wrapper: ReturnType<typeof mountDialog>, providerId: string) {
  await wrapper.find('#model-provider').setValue(providerId)
  await wrapper.find('#model-api-key').setValue('sk-test-key')
}

async function clickSave(wrapper: ReturnType<typeof mountDialog>) {
  const saveButton = wrapper.findAll('button').find((node) => node.text() === '保存配置')
  await saveButton?.trigger('click')
  await flushPromises()
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

    await fillPresetForm(wrapper, 'deepseek')
    await clickSave(wrapper)

    expect(settingsApi.saveModelConfig).toHaveBeenCalledWith({
      llm_api_base: 'https://api.deepseek.com/v1',
      llm_api_key: 'sk-test-key',
      llm_model: 'deepseek-chat',
    })
  })

  it('does not render a model dropdown for preset providers', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    await fillPresetForm(wrapper, 'deepseek')
    expect(wrapper.find('#model-preset-model').exists()).toBe(false)
  })

  it('does not render the LLM summary box', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue({
      ...baseConfig,
      llm_api_base: 'https://api.deepseek.com/v1',
      llm_model: 'deepseek-chat',
      llm_source: 'user',
    })
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('.model-dialog__current').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('大模型')
  })
})
