import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FormSelect from '@/components/FormSelect.vue'
import type { SelectOption } from '@/types/ui'

const options: SelectOption[] = [
  { value: 'scheduled', label: '进行中' },
  { value: 'archived', label: '已归档' },
]

describe('FormSelect', () => {
  it('renders the label and options', () => {
    const wrapper = mount(FormSelect, {
      props: { id: 'status', label: '状态', options, modelValue: 'scheduled' },
    })
    expect(wrapper.get('label').text()).toContain('状态')
    expect(wrapper.findAll('option')).toHaveLength(2)
  })

  it('renders a disabled placeholder option when provided', () => {
    const wrapper = mount(FormSelect, {
      props: { id: 'status', label: '状态', options, placeholder: '全部', modelValue: '' },
    })
    const placeholder = wrapper.get('option')
    expect(placeholder.text()).toBe('全部')
    expect(placeholder.attributes('disabled')).toBeDefined()
  })

  it('emits update:modelValue on change', async () => {
    const wrapper = mount(FormSelect, {
      props: { id: 'status', label: '状态', options, modelValue: 'scheduled' },
    })
    await wrapper.get('select').setValue('archived')
    expect(wrapper.emitted('update:modelValue')).toEqual([['archived']])
  })

  it('shows an error and marks the control invalid', () => {
    const wrapper = mount(FormSelect, {
      props: { id: 'status', label: '状态', options, modelValue: '', error: '请选择状态' },
    })
    expect(wrapper.get('.form-field__error').text()).toBe('请选择状态')
    expect(wrapper.get('select').attributes('aria-invalid')).toBe('true')
  })
})
