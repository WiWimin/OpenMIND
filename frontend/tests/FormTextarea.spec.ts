import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FormTextarea from '@/components/FormTextarea.vue'

describe('FormTextarea', () => {
  it('renders the label and value', () => {
    const wrapper = mount(FormTextarea, {
      props: { id: 'content', label: '记录内容', modelValue: '正文' },
    })
    expect(wrapper.get('label').text()).toContain('记录内容')
    expect(wrapper.get('textarea').element.value).toBe('正文')
  })

  it('applies the rows attribute', () => {
    const wrapper = mount(FormTextarea, {
      props: { id: 'content', label: '记录内容', modelValue: '', rows: 6 },
    })
    expect(wrapper.get('textarea').attributes('rows')).toBe('6')
  })

  it('emits update:modelValue on input', async () => {
    const wrapper = mount(FormTextarea, {
      props: { id: 'content', label: '记录内容', modelValue: '' },
    })
    await wrapper.get('textarea').setValue('新的记录')
    expect(wrapper.emitted('update:modelValue')).toEqual([['新的记录']])
  })

  it('shows an error and marks the control invalid', () => {
    const wrapper = mount(FormTextarea, {
      props: { id: 'content', label: '记录内容', modelValue: '', error: '内容不能为空' },
    })
    expect(wrapper.get('.form-field__error').text()).toBe('内容不能为空')
    expect(wrapper.get('textarea').attributes('aria-invalid')).toBe('true')
  })
})
