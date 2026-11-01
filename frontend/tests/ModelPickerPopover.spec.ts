import { flushPromises, mount } from '@vue/test-utils'
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
  getProviderModels: vi.fn(),
}))

const mockedGet = vi.mocked(settingsApi.getModelConfig)
const mockedProviderModels = vi.mocked(settingsApi.getProviderModels)

function config(overrides: Partial<ModelConfig> = {}): ModelConfig {
  return {
    llm_api_base: 'https://api.deepseek.com/v1',
    llm_model: 'deepseek-chat',
    llm_api_key_masked: '',
    llm_source: 'user',
    llm_purpose_models: {},
    embedding_api_base: '',
    embedding_model: '',
    embedding_api_key_masked: '',
    embedding_source: 'none',
    embedding_dim: 1024,
    ...overrides,
  }
}

function itemLabels(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper.findAll('.model-picker__item').map((item) => item.text())
}

beforeEach(() => {
  mockedGet.mockReset()
  mockedProviderModels.mockReset()
})

describe('ModelPickerPopover', () => {
  it('loads the config on mount and selects the first provider model by default', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockResolvedValue({
      llm_model: 'deepseek-chat',
      models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-v3.2'],
    })
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(1)
    // 默认选中「全部模型」的第一个模型，并同步给父组件
    expect(wrapper.emitted('select')).toEqual([['deepseek-chat']])
    expect(wrapper.get('.model-picker__label').text()).toBe('deepseek-chat')
    expect(wrapper.find('.model-picker__panel').exists()).toBe(false)
  })

  it('keeps the saved default as the trigger label when the catalog fails', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockRejectedValue(new Error('boom'))
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    expect(wrapper.emitted('select')).toBeUndefined()
    expect(wrapper.get('.model-picker__label').text()).toBe('deepseek-chat')
  })

  it('opens a window with a search box and an add-config button', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockResolvedValue({
      llm_model: 'deepseek-chat',
      models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-v3.2'],
    })
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')

    expect(wrapper.get('.model-picker__search-input').attributes('placeholder')).toBe('搜索模型')
    expect(wrapper.get('.model-picker__add').attributes('title')).toBe('添加模型配置')

    const labels = itemLabels(wrapper)
    // 只保留「全部模型」组：无默认项、无项目预设组
    expect(labels.some((text) => text.includes('默认（按用途路由）'))).toBe(false)
    expect(wrapper.findAll('.model-picker__group').length).toBe(1)
    expect(wrapper.get('.model-picker__group').text()).toBe('全部模型')
    expect(labels.length).toBe(3)
    expect(labels.some((text) => text.includes('deepseek-v3.2'))).toBe(true)
  })

  it('emits the selection and closes the window', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockResolvedValue({
      llm_model: 'deepseek-chat',
      models: ['deepseek-chat', 'deepseek-reasoner'],
    })
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')
    const items = wrapper.findAll('.model-picker__item')
    await items[1].trigger('click')

    // 第一次是挂载后的默认选中，第二次是用户点击
    expect(wrapper.emitted('select')?.at(-1)).toEqual(['deepseek-reasoner'])
    expect(wrapper.find('.model-picker__panel').exists()).toBe(false)
  })

  it('filters models by the search query', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockResolvedValue({
      llm_model: 'deepseek-chat',
      models: ['deepseek-chat', 'deepseek-reasoner'],
    })
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')
    await wrapper.get('.model-picker__search-input').setValue('reasoner')

    const labels = itemLabels(wrapper)
    expect(labels.length).toBe(1)
    expect(labels[0]).toContain('deepseek-reasoner')
  })

  it('emits manage and closes when the add button is clicked', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockResolvedValue({ llm_model: 'deepseek-chat', models: [] })
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')
    await wrapper.get('.model-picker__add').trigger('click')

    expect(wrapper.emitted('manage')).toEqual([[]])
    expect(wrapper.find('.model-picker__panel').exists()).toBe(false)
  })

  it('shows an error state when loading fails', async () => {
    mockedGet.mockRejectedValue(new Error('boom'))
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')
    expect(wrapper.get('.model-picker__state--error').text()).toContain('加载失败')
  })

  it('shows the provider error and an empty list when the catalog fails', async () => {
    mockedGet.mockResolvedValue(config())
    mockedProviderModels.mockRejectedValue(new Error('boom'))
    const wrapper = mount(ModelPickerPopover, mountOptions)
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')

    expect(wrapper.get('.model-picker__state--error').text()).toContain('获取服务商模型列表失败')
    expect(wrapper.findAll('.model-picker__item').length).toBe(0)
  })

  it('does not open when disabled', async () => {
    mockedGet.mockResolvedValue(config())
    const wrapper = mount(ModelPickerPopover, { props: { disabled: true }, ...mountOptions })
    await flushPromises()

    await wrapper.get('.model-picker__trigger').trigger('click')

    expect(wrapper.find('.model-picker__panel').exists()).toBe(false)
  })
})
