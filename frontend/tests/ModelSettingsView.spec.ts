import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as settingsApi from '@/api/settings'
import type { ModelConfigRead } from '@/types/modelConfig'
import ModelSettingsView from '@/views/settings/ModelSettingsView.vue'

vi.mock('@/api/settings', () => ({
  getModelConfig: vi.fn(),
  saveModelConfig: vi.fn(),
  clearModelConfig: vi.fn(),
}))

const config: ModelConfigRead = {
  llm_api_base: 'https://llm.example.com/v1',
  llm_model: 'gpt-4o-mini',
  llm_api_key_masked: 'sk-...abcd',
  embedding_api_base: 'https://emb.example.com/v1',
  embedding_model: 'text-embedding-v3',
  embedding_api_key_masked: 'sk-...wxyz',
  embedding_dim: 1024,
}

function mountView(): VueWrapper {
  return mount(ModelSettingsView)
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('ModelSettingsView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows the effective config with masked keys', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(config)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('模型设置')
    expect(wrapper.text()).toContain('https://llm.example.com/v1')
    expect(wrapper.text()).toContain('gpt-4o-mini')
    expect(wrapper.text()).toContain('sk-...abcd')
    expect(wrapper.text()).toContain('1024')
  })

  it('saves only the enabled provider', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(config)
    vi.mocked(settingsApi.saveModelConfig).mockResolvedValue({
      ...config,
      llm_api_base: 'https://new.example.com/v1',
      llm_model: 'new-model',
      llm_api_key_masked: 'sk-...new',
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#use-llm').setValue(true)
    await wrapper.get('#llm-api-base').setValue('https://new.example.com/v1')
    await wrapper.get('#llm-model').setValue('new-model')
    await wrapper.get('#llm-api-key').setValue('sk-new-secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(settingsApi.saveModelConfig).toHaveBeenCalledWith({
      llm_api_base: 'https://new.example.com/v1',
      llm_api_key: 'sk-new-secret',
      llm_model: 'new-model',
    })
    expect(wrapper.text()).toContain('https://new.example.com/v1')
  })

  it('requires all fields for an enabled provider', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(config)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#use-llm').setValue(true)
    await wrapper.get('#llm-api-base').setValue('https://new.example.com/v1')
    await wrapper.get('#llm-model').setValue('')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(settingsApi.saveModelConfig).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请填写 API Key')
    expect(wrapper.text()).toContain('请填写模型名称')
  })

  it('clears the user config after confirmation', async () => {
    vi.mocked(settingsApi.getModelConfig).mockResolvedValue(config)
    vi.mocked(settingsApi.clearModelConfig).mockResolvedValue({ deleted: true })
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '清除我的配置')?.trigger('click')
    await flushPromises()
    await button(wrapper, '清除')?.trigger('click')
    await flushPromises()

    expect(settingsApi.clearModelConfig).toHaveBeenCalledTimes(1)
    expect(settingsApi.getModelConfig).toHaveBeenCalledTimes(2)
  })
})
