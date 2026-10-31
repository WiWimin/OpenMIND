import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TemplatePickerPopover from '@/components/TemplatePickerPopover.vue'
import * as templatesApi from '@/api/templates'
import type { MeetingTemplate } from '@/types/template'

const mountOptions = {
  global: {
    stubs: { RouterLink: true },
  },
}

vi.mock('@/api/templates', () => ({
  listTemplates: vi.fn(),
}))

const mockedList = vi.mocked(templatesApi.listTemplates)

function template(overrides: Partial<MeetingTemplate> = {}): MeetingTemplate {
  return {
    template_id: 'tpl_custom_1',
    name: '我的模板',
    description: '自定义结构',
    source: 'custom',
    file_name: 'mine.txt',
    created_at: '2026-10-29T00:00:00Z',
    ...overrides,
  }
}

beforeEach(() => {
  mockedList.mockReset()
})

describe('TemplatePickerPopover', () => {
  it('loads templates lazily and emits selection', async () => {
    mockedList.mockResolvedValue([
      template(),
      template({
        template_id: 'tpl-builtin-standard-minutes',
        name: '标准会议纪要',
        source: 'builtin',
        file_name: null,
        created_at: null,
      }),
    ])
    const wrapper = mount(TemplatePickerPopover, mountOptions)

    await wrapper.get('.template-picker__trigger').trigger('click')
    await vi.waitFor(() => {
      expect(mockedList).toHaveBeenCalledTimes(1)
    })

    const names = wrapper.findAll('.template-picker__item strong').map((node) => node.text())
    expect(names).toContain('我的模板')
    expect(names).toContain('标准会议纪要')
    expect(names).toContain('默认结构')

    const items = wrapper.findAll('.template-picker__item')
    await items[0].trigger('click')

    expect(wrapper.emitted('select')).toEqual([['tpl_custom_1']])
    expect(wrapper.find('.template-picker__panel').exists()).toBe(false)
  })

  it('emits empty id when choosing the default structure', async () => {
    mockedList.mockResolvedValue([template()])
    const wrapper = mount(TemplatePickerPopover, mountOptions)

    await wrapper.get('.template-picker__trigger').trigger('click')
    await vi.waitFor(() => {
      expect(wrapper.findAll('.template-picker__item').length).toBe(2)
    })

    const defaultItem = wrapper
      .findAll('.template-picker__item')
      .find((item) => item.text().includes('默认结构'))
    await defaultItem?.trigger('click')

    expect(wrapper.emitted('select')).toEqual([['']])
  })

  it('shows an error state when loading fails', async () => {
    mockedList.mockRejectedValue(new Error('boom'))
    const wrapper = mount(TemplatePickerPopover, mountOptions)

    await wrapper.get('.template-picker__trigger').trigger('click')
    await vi.waitFor(() => {
      expect(wrapper.get('.template-picker__state--error').text()).toContain('加载失败')
    })
  })
})
