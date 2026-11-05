import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as templatesApi from '@/api/templates'
import TemplateFormDialog from '@/components/settings/TemplateFormDialog.vue'
import { useToast } from '@/composables/useToast'
import type { MeetingTemplate } from '@/types/template'

vi.mock('@/api/templates', () => ({
  createTemplateText: vi.fn(),
  generateTemplate: vi.fn(),
}))

const mockedCreate = vi.mocked(templatesApi.createTemplateText)
const mockedGenerate = vi.mocked(templatesApi.generateTemplate)

function mountDialog(props: { open: boolean; initialTab?: 'manual' | 'ai' } = { open: true }) {
  return mount(TemplateFormDialog, { props })
}

const created: MeetingTemplate = {
  template_id: 'tpl_new',
  name: '评审会纪要',
  description: null,
  category: '会后',
  source: 'custom',
  file_name: null,
  created_at: null,
  content_preview: '1. 评审结论',
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('TemplateFormDialog', () => {
  it('creates a template from the manual form', async () => {
    mockedCreate.mockResolvedValue(created)
    const wrapper = mountDialog()

    await wrapper.get('#template-form-name').setValue('评审会纪要')
    await wrapper.get('#template-form-content').setValue('1. 评审结论；2. 问题清单')
    await wrapper.findAll('button').find((node) => node.text() === '保存模板')?.trigger('click')
    await flushPromises()

    expect(mockedCreate).toHaveBeenCalledWith({
      name: '评审会纪要',
      description: undefined,
      category: '通用',
      content_text: '1. 评审结论；2. 问题清单',
    })
    expect(useToast().toasts.value.some((t) => t.message.includes('模板已创建'))).toBe(true)
    expect(wrapper.emitted('created')).toEqual([[]])
  })

  it('fills the form with the AI draft before saving', async () => {
    mockedGenerate.mockResolvedValue({
      name: '周会复盘',
      description: '适用于每周例会',
      category: '会后',
      content_text: '1. 数据回顾；2. 改进项',
    })
    mockedCreate.mockResolvedValue(created)
    const wrapper = mountDialog({ open: true, initialTab: 'ai' })

    await wrapper.get('#template-form-ai-desc').setValue('周会复盘模板')
    await wrapper.findAll('button').find((node) => node.text() === '生成草稿')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已生成草稿')
    expect((wrapper.get('#template-form-ai-name').element as HTMLInputElement).value).toBe(
      '周会复盘',
    )

    await wrapper.findAll('button').find((node) => node.text() === '保存模板')?.trigger('click')
    await flushPromises()

    expect(mockedCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: '周会复盘', category: '会后' }),
    )
  })

  it('disables saving before an AI draft is generated', () => {
    const wrapper = mountDialog({ open: true, initialTab: 'ai' })

    const saveButton = wrapper
      .findAll('button')
      .find((node) => node.text() === '保存模板')
    expect(saveButton?.attributes('disabled')).toBeDefined()
  })

  it('shows a validation error when name or content is missing', async () => {
    const wrapper = mountDialog()

    await wrapper.findAll('button').find((node) => node.text() === '保存模板')?.trigger('click')

    expect(wrapper.get('.template-form__error').text()).toContain('请填写模板名称与内容')
    expect(mockedCreate).not.toHaveBeenCalled()
  })
})
