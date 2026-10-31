import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ModelPickerPopover from '@/components/ModelPickerPopover.vue'
import * as settingsApi from '@/api/settings'
import type { ModelConfig } from '@/types/modelConfig'

const mountOptions = {
  global: {
    stubs: { RouterLink: true },
  },
}

vi.mock('@/api/settings', () => ({
  getModelConfig: vi.fn(),
}))

const mockedGet = vi.mocked(settingsApi.getModelConfig)

function config(overrides: Partial<ModelConfig> = {}): ModelConfig {
  return {
    llm_api_base: 'https://llm.example.com',
    llm_model: 'global-model',
    llm_api_key_masked: '',
    llm_source: 'user',
    llm_purpose_models: { chat: 'chat-model' },
    embedding_api_base: '',
    embedding_model: '',
    embedding_api_key_masked: '',
    embedding_source: 'none',
    embedding_dim: 1024,
    ...overrides,
  }
}

beforeEach(() => {
  mockedGet.mockReset()
})

describe('ModelPickerPopover', () => {
  it('loads model options lazily when opened and emits selection', async () => {
    mockedGet.mockResolvedValue(config())
    const wrapper = mount(ModelPickerPopover, mountOptions)

    await wrapper.get('.model-picker__trigger').trigger('click')
    await vi.waitFor(() => {
      expect(mockedGet).toHaveBeenCalledTimes(1)
    })

    const labels = wrapper.findAll('.model-picker__item').map((item) => item.text())
    expect(labels.some((text) => text.includes('默认（按用途路由）'))).toBe(true)
    expect(labels.some((text) => text.includes('global-model'))).toBe(true)
    expect(labels.some((text) => text.includes('chat-model'))).toBe(true)

    const items = wrapper.findAll('.model-picker__item')
    await items[1].trigger('click')

    expect(wrapper.emitted('select')).toEqual([['global-model']])
    expect(wrapper.find('.model-picker__panel').exists()).toBe(false)
  })

  it('marks the selected model with an active trigger', async () => {
    mockedGet.mockResolvedValue(config())
    const wrapper = mount(ModelPickerPopover, { props: { selected: 'chat-model' }, ...mountOptions })

    expect(wrapper.find('.model-picker__trigger--active').exists()).toBe(true)

    await wrapper.get('.model-picker__trigger').trigger('click')
    await vi.waitFor(() => {
      expect(wrapper.findAll('.model-picker__item--selected').length).toBe(1)
    })
  })

  it('shows an error state when loading fails', async () => {
    mockedGet.mockRejectedValue(new Error('boom'))
    const wrapper = mount(ModelPickerPopover, mountOptions)

    await wrapper.get('.model-picker__trigger').trigger('click')
    await vi.waitFor(() => {
      expect(wrapper.get('.model-picker__state--error').text()).toContain('加载失败')
    })
  })

  it('does not open when disabled', async () => {
    const wrapper = mount(ModelPickerPopover, { props: { disabled: true }, ...mountOptions })
    await wrapper.get('.model-picker__trigger').trigger('click')

    expect(wrapper.find('.model-picker__panel').exists()).toBe(false)
    expect(mockedGet).not.toHaveBeenCalled()
  })
})
