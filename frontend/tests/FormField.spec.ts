import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FormField from '@/components/FormField.vue'

describe('FormField', () => {
  it('emits updates through v-model', async () => {
    const wrapper = mount(FormField, {
      props: { id: 'name', label: '用户名', modelValue: '' },
    })

    await wrapper.get('input').setValue('Alice')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['Alice'])
  })

  it('renders the label and marks the input invalid on error', () => {
    const wrapper = mount(FormField, {
      props: { id: 'name', label: '用户名', modelValue: '', error: '请输入用户名' },
    })

    expect(wrapper.get('label').text()).toContain('用户名')
    expect(wrapper.get('input').attributes('aria-invalid')).toBe('true')
    expect(wrapper.text()).toContain('请输入用户名')
  })
})
