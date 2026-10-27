import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as settingsApi from '@/api/settings'
import type { ModelConfig } from '@/types/modelConfig'
import ModelSettingsView from '@/views/settings/ModelSettingsView.vue'

vi.mock('@/api/settings', () => ({
  getModelConfig: vi.fn(),
  saveModelConfig: vi.fn(),
  savePurposeModels: vi.fn(),
  clearModelConfig: vi.fn(),
}))

const configUser: ModelConfig = {
  llm_api_base: 'https://llm.example.com/v1',
  llm_model: 'custom-model',
  llm_api_key_masked: 'sk-...-key',
  llm_source: 'user',
  llm_purpose_models: { minutes: 'minutes-model' },
  embedding_api_base: 'https://emb.example.com/v1',
  embedding_model: 'text-embedding-1024',
  embedding_api_key_masked: 'sk-...-key',
  embedding_source: 'user',
  embedding_dim: 1024,
}

const configEmpty: ModelConfig = {
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

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(ModelSettingsView, { global: { plugins: [pinia] } })
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll('button').find((item) => item.text().includes(text))
  if (!button) {
    throw new Error(`button not found: ${text}`)
  }
  return button
}

describe('ModelSettingsView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders both provider cards with their source labels', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(configUser)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('大模型（LLM）')
    expect(wrapper.text()).toContain('向量模型（Embedding）')
    expect(wrapper.text()).toContain('用户配置')
    expect(wrapper.text()).toContain('custom-model')
    expect(wrapper.text()).toContain('按用途模型')
    expect((wrapper.get('#purpose-minutes').element as HTMLInputElement).value).toBe(
      'minutes-model',
    )
  })

  it('saves purpose model overrides', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(configUser)
    vi.mocked(settingsApi.savePurposeModels).mockResolvedValue({
      ...configUser,
      llm_purpose_models: { minutes: 'minutes-model', chat: 'chat-model' },
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#purpose-chat').setValue('chat-model')
    await buttonByText(wrapper, '保存用途模型').trigger('click')
    await flushPromises()

    expect(settingsApi.savePurposeModels).toHaveBeenCalledWith({
      models: { minutes: 'minutes-model', chat: 'chat-model' },
    })
  })

  it('blocks saving a provider that is only partially filled', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(configEmpty)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#llm-api-base').setValue('https://llm.example.com/v1')
    await buttonByText(wrapper, '保存配置').trigger('click')

    expect(settingsApi.saveModelConfig).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请完整填写')
  })

  it('saves a fully specified provider and omits the untouched one', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(configEmpty)
    vi.mocked(settingsApi.saveModelConfig).mockResolvedValue(configUser)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#llm-api-base').setValue('https://llm.example.com/v1')
    await wrapper.get('#llm-api-key').setValue('sk-1')
    await wrapper.get('#llm-model').setValue('custom-model')
    await buttonByText(wrapper, '保存配置').trigger('click')
    await flushPromises()

    expect(settingsApi.saveModelConfig).toHaveBeenCalledWith({
      llm_api_base: 'https://llm.example.com/v1',
      llm_api_key: 'sk-1',
      llm_model: 'custom-model',
    })
  })

  it('asks for confirmation before clearing a user-configured provider', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(configUser)
    vi.mocked(settingsApi.saveModelConfig).mockResolvedValue(configUser)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#llm-api-base').setValue('https://llm.example.com/v1')
    await wrapper.get('#llm-api-key').setValue('sk-1')
    await wrapper.get('#llm-model').setValue('custom-model')
    await buttonByText(wrapper, '保存配置').trigger('click')

    expect(settingsApi.saveModelConfig).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('确认清除提供方')

    await buttonByText(wrapper, '继续保存').trigger('click')
    await flushPromises()

    expect(settingsApi.saveModelConfig).toHaveBeenCalledWith({
      llm_api_base: 'https://llm.example.com/v1',
      llm_api_key: 'sk-1',
      llm_model: 'custom-model',
    })
  })

  it('resets to the server default after confirmation', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(configUser)
    vi.mocked(settingsApi.clearModelConfig).mockResolvedValue({ deleted: true })
    const wrapper = mountView()
    await flushPromises()

    await buttonByText(wrapper, '恢复服务端默认').trigger('click')
    await buttonByText(wrapper, '恢复默认').trigger('click')
    await flushPromises()

    expect(settingsApi.clearModelConfig).toHaveBeenCalledTimes(1)
  })

  it('offers a reset action when existing encrypted config cannot be read', async () => {
    vi.mocked(settingsApi.getModelConfig)
      .mockRejectedValueOnce({
        status: 'error',
        error_code: 'MODEL_CONFIG_INVALID',
        message: '模型密钥无法解密，请重新保存模型配置',
        retryable: false,
      })
      .mockResolvedValueOnce(configEmpty)
    vi.mocked(settingsApi.clearModelConfig).mockResolvedValue({ deleted: true })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('模型密钥无法解密')
    await buttonByText(wrapper, '恢复服务端默认').trigger('click')
    await buttonByText(wrapper, '恢复默认').trigger('click')
    await flushPromises()

    expect(settingsApi.clearModelConfig).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('模型密钥无法解密')
  })
})
