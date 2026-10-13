import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppButton from '@/components/AppButton.vue'

describe('AppButton', () => {
  it('renders slot content', () => {
    const wrapper = mount(AppButton, { slots: { default: '保存' } })
    expect(wrapper.text()).toContain('保存')
  })

  it('is disabled while loading', () => {
    const wrapper = mount(AppButton, {
      props: { loading: true },
      slots: { default: '提交' },
    })
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })
})
